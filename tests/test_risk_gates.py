"""Tests for risk gates and position sizing in kalshi_executor.py.

These protect real money — every rejection path must work correctly.
"""

import os
import pytest
from unittest.mock import patch

from datetime import datetime, timedelta, timezone

from opportunity import Opportunity
from kalshi_executor import (
    unit_size_contracts, size_order, SizedOrder,
    trusted_edge, min_edge_for,
    matchup_key, recent_matchups_from_log,
    cancel_stale_resting_orders,
    dedup_correlated_brackets,
    preflight_gate_status,
    _apply_budget_cap,
)
from kalshi_client import KalshiAPIError


@pytest.fixture
def sizing_defaults(monkeypatch):
    """Pin the sizing knobs to the documented code defaults.

    Any test asserting a bare ``"APPROVED"`` verdict is implicitly asserting
    that no *sizing cap* fired — but ``MAX_BET_SIZE`` and ``KELLY_FRACTION``
    are module globals snapshotted from the operator's live ``.env`` at import
    time. Without pinning, a bankroll experiment silently breaks gate tests
    that have nothing to do with sizing.

    This has now bitten twice: 2026-07-22 (KELLY_FRACTION 0.25 -> 1 broke the
    venue-min-shares class, see ``_pin_kelly``) and 2026-07-27 (C11, where
    MAX_BET_SIZE 15 -> 8 plus the Kelly price-complement fix pushed twelve
    gate tests into ``APPROVED_CAPPED_MAX_BET``). Classes that assert clean
    approvals should depend on this rather than inherit the .env of the day.
    """
    import kalshi_executor as ke
    monkeypatch.setattr(ke, "MAX_BET_SIZE", 100.0)
    monkeypatch.setattr(ke, "KELLY_FRACTION", 0.25)


# ── unit_size_contracts ──────────────────────────────────────────────────────

class TestUnitSizeContracts:
    def test_standard_price(self):
        # $0.50 price, $1 unit → 2 contracts
        assert unit_size_contracts(0.50, 1.00) == 2

    def test_cheap_price(self):
        # $0.02 price, $1 unit → 50 contracts
        assert unit_size_contracts(0.02, 1.00) == 50

    def test_moderate_price(self):
        # $0.03 price, $1 unit → 33 contracts
        assert unit_size_contracts(0.03, 1.00) == 33

    def test_expensive_price(self):
        # $0.90 price, $1 unit → 1 contract
        assert unit_size_contracts(0.90, 1.00) == 1

    def test_minimum_one_contract(self):
        # Even at high price, at least 1 contract
        assert unit_size_contracts(0.99, 0.50) >= 1

    def test_zero_price_returns_zero(self):
        assert unit_size_contracts(0.0, 1.00) == 0

    def test_negative_price_returns_zero(self):
        assert unit_size_contracts(-0.10, 1.00) == 0

    def test_price_at_one_returns_zero(self):
        assert unit_size_contracts(1.0, 1.00) == 0

    def test_price_above_one_returns_zero(self):
        assert unit_size_contracts(1.50, 1.00) == 0

    def test_half_dollar_unit(self):
        # $0.50 price, $0.50 unit → 1 contract
        assert unit_size_contracts(0.50, 0.50) == 1

    def test_large_unit(self):
        # $0.25 price, $5 unit → 20 contracts
        assert unit_size_contracts(0.25, 5.00) == 20


# ── size_order risk gates ────────────────────────────────────────────────────

class TestSizeOrderRiskGates:
    """Test that each risk gate correctly rejects or approves."""

    @pytest.fixture(autouse=True)
    def _pin_sizing(self, sizing_defaults):
        """These cases assert gate verdicts, not sizing — see `sizing_defaults`."""

    def _make_opp(self, edge=0.10, confidence="high", score=8.0, price=0.50):
        return Opportunity(
            ticker="KXMLBGAME-99MAR301840CWSMIA-MIA",
            title="Test Game",
            category="game",
            side="yes",
            market_price=price,
            fair_value=price + edge,
            edge=edge,
            edge_source="test",
            confidence=confidence,
            liquidity_score=8.0,
            composite_score=score,
            details={},
        )

    @patch.dict(os.environ, {"MAX_DAILY_LOSS": "250", "MAX_OPEN_POSITIONS": "50",
                              "MIN_EDGE_THRESHOLD": "0.03", "MIN_COMPOSITE_SCORE": "6.0"})
    def test_approved_when_all_gates_pass(self):
        opp = self._make_opp(edge=0.10, confidence="high", score=8.0)
        result = size_order(opp, bankroll=100.0, open_positions=5, daily_pnl=0.0)
        assert result.risk_approval == "APPROVED"
        assert result.contracts >= 1

    @patch.dict(os.environ, {"MAX_DAILY_LOSS": "250"})
    def test_rejected_daily_loss_limit(self):
        opp = self._make_opp()
        result = size_order(opp, bankroll=100.0, open_positions=5, daily_pnl=-260.0)
        assert result.risk_approval != "APPROVED"
        assert "daily_loss" in result.risk_approval.lower()

    def test_rejected_max_positions(self):
        import kalshi_executor
        original = kalshi_executor.MAX_OPEN_POSITIONS
        try:
            kalshi_executor.MAX_OPEN_POSITIONS = 10
            opp = self._make_opp()
            result = size_order(opp, bankroll=100.0, open_positions=10, daily_pnl=0.0)
            assert result.risk_approval != "APPROVED"
            assert "position" in result.risk_approval.lower()
        finally:
            kalshi_executor.MAX_OPEN_POSITIONS = original

    @patch.dict(os.environ, {"MIN_EDGE_THRESHOLD": "0.05"})
    def test_rejected_below_edge_threshold(self):
        opp = self._make_opp(edge=0.02)
        result = size_order(opp, bankroll=100.0, open_positions=5, daily_pnl=0.0)
        assert result.risk_approval != "APPROVED"
        assert "edge" in result.risk_approval.lower()

    @patch.dict(os.environ, {"MIN_COMPOSITE_SCORE": "7.0"})
    def test_rejected_below_min_score(self):
        opp = self._make_opp(score=5.0)
        result = size_order(opp, bankroll=100.0, open_positions=5, daily_pnl=0.0)
        assert result.risk_approval != "APPROVED"
        assert "score" in result.risk_approval.lower()

    def test_contracts_capped_by_bankroll(self):
        # Very cheap price with tiny bankroll. Disable the R7 price floor so we're
        # exercising the bankroll cap rather than the lottery-ticket gate.
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.0
            opp = self._make_opp(price=0.02, edge=0.10, score=8.0)
            result = size_order(opp, bankroll=0.05, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            # Should not size more than bankroll allows
            assert result.cost_dollars <= 0.05 + 0.01  # small float tolerance
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor

    def test_price_clamped_to_valid_range(self):
        # Price at extreme low. Disable the R7 price floor so we're exercising
        # the price-clamp logic rather than the lottery-ticket gate.
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.0
            opp = self._make_opp(price=0.005, edge=0.10, score=8.0)
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.price_cents >= 1
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor

    def test_approved_clean_when_no_caps_hit(self):
        # Small bet, big bankroll — pin MAX_BET_SIZE and KELLY_FRACTION to documented
        # defaults so the test is independent of the developer's local .env
        # (which may set e.g. MAX_BET_SIZE=15 or KELLY_FRACTION=1.0 and trigger the cap).
        import kalshi_executor
        orig_max = kalshi_executor.MAX_BET_SIZE
        orig_kelly = kalshi_executor.KELLY_FRACTION
        orig_edge = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor.MAX_BET_SIZE = 100.0
            kalshi_executor.KELLY_FRACTION = 0.25
            # Clear per-sport floors too: edge=0.05 is above the global 3% floor
            # but below MLB's .env override (0.08), and this test asserts a clean
            # approval under documented defaults — not whatever .env sets.
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            opp = self._make_opp(price=0.50, edge=0.05, score=8.0)
            result = size_order(opp, bankroll=500.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig_edge)
            kalshi_executor.MAX_BET_SIZE = orig_max
            kalshi_executor.KELLY_FRACTION = orig_kelly

    def test_approved_capped_max_bet(self):
        # Big Kelly bet hits the max bet cap
        import kalshi_executor
        orig_max = kalshi_executor.MAX_BET_SIZE
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MAX_BET_SIZE = 5.0  # low cap
            kalshi_executor.MIN_MARKET_PRICE = 0.0  # this test exercises the cap, not the R7 floor
            opp = self._make_opp(price=0.10, edge=0.50, score=9.0)
            result = size_order(opp, bankroll=500.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED_CAPPED_MAX_BET"
            assert result.cost_dollars <= 5.0 + 0.11
        finally:
            kalshi_executor.MAX_BET_SIZE = orig_max
            kalshi_executor.MIN_MARKET_PRICE = orig_floor


# ── R7: Minimum market-price floor (Gate 3.5) ────────────────────────────────

class TestMinMarketPriceGate:
    """Gate 3.5: reject opportunities whose market price is below MIN_MARKET_PRICE.

    F10 from the 2026-04-21 14-day review: sub-10¢ bets went 1W-3L while the
    model claimed '+50% edge' on 8-10¢ longshots. Hard reject, no exception for
    edge or confidence (unlike Gate 4.6 which has an exception clause).
    """

    def _opp(self, price: float) -> Opportunity:
        return Opportunity(
            ticker="KXMLBGAME-99MAR301840CWSMIA-MIA",
            title="Test Game",
            category="game",
            side="yes",
            market_price=price,
            fair_value=price + 0.15,  # healthy edge so edge gate passes
            edge=0.15,
            edge_source="test",
            confidence="high",
            liquidity_score=8.0,
            composite_score=8.5,
            details={},
        )

    def test_rejected_below_floor(self):
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.10
            result = size_order(self._opp(price=0.05), bankroll=500.0,
                                open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval.startswith("REJECTED")
            assert "price_below_floor" in result.risk_approval
            assert result.contracts == 0
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor

    def test_rejected_just_below_floor(self):
        # 9¢ is rejected; 10¢ is not (strict less-than, floor inclusive).
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.10
            result = size_order(self._opp(price=0.09), bankroll=500.0,
                                open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert "price_below_floor" in result.risk_approval
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor

    def test_approved_at_floor(self):
        # Exactly at floor should pass (user preference: "I like .10").
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.10
            result = size_order(self._opp(price=0.10), bankroll=500.0,
                                open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED" or result.risk_approval.startswith("APPROVED_CAPPED")
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor

    def test_approved_above_floor(self):
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        orig_max = kalshi_executor.MAX_BET_SIZE
        orig_kelly = kalshi_executor.KELLY_FRACTION
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.10
            kalshi_executor.MAX_BET_SIZE = 100.0
            kalshi_executor.KELLY_FRACTION = 0.25
            result = size_order(self._opp(price=0.50), bankroll=500.0,
                                open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor
            kalshi_executor.MAX_BET_SIZE = orig_max
            kalshi_executor.KELLY_FRACTION = orig_kelly

    def test_disabled_when_zero(self):
        # MIN_MARKET_PRICE=0 disables the gate entirely (preserve longshots).
        import kalshi_executor
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.MIN_MARKET_PRICE = 0.0
            result = size_order(self._opp(price=0.03), bankroll=500.0,
                                open_positions=0, daily_pnl=0.0, unit_size=1.00)
            # Gate 3.5 inactive — any rejection must come from another gate,
            # not from price_below_floor.
            assert "price_below_floor" not in result.risk_approval
        finally:
            kalshi_executor.MIN_MARKET_PRICE = orig_floor


# ── R3: Minimum confidence gate ──────────────────────────────────────────────

class TestMinConfidenceGate:
    """Gate 4.5: reject opportunities whose confidence falls below MIN_CONFIDENCE."""

    @pytest.fixture(autouse=True)
    def _pin_sizing(self, sizing_defaults):
        """These cases assert gate verdicts, not sizing — see `sizing_defaults`."""

    def _opp(self, confidence: str) -> Opportunity:
        return Opportunity(
            ticker="KXMLBGAME-26APR21NYYKAC-NYY",
            title="Test", category="game", side="yes",
            market_price=0.50, fair_value=0.60, edge=0.10,
            edge_source="test", confidence=confidence,
            liquidity_score=8.0, composite_score=8.0, details={},
        )

    def test_rejects_low_when_min_is_medium(self):
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "medium"
            result = size_order(self._opp("low"), bankroll=100.0,
                                open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("REJECTED")
            assert "confidence" in result.risk_approval.lower()
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig

    def test_approves_medium_when_min_is_medium(self):
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "medium"
            result = size_order(self._opp("medium"), bankroll=100.0,
                                open_positions=0, daily_pnl=0.0)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig

    def test_approves_high_when_min_is_medium(self):
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "medium"
            result = size_order(self._opp("high"), bankroll=100.0,
                                open_positions=0, daily_pnl=0.0)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig

    def test_rejects_low_and_medium_when_min_is_high(self):
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "high"
            for conf in ("low", "medium"):
                result = size_order(self._opp(conf), bankroll=100.0,
                                    open_positions=0, daily_pnl=0.0)
                assert result.risk_approval.startswith("REJECTED"), conf
                assert "confidence" in result.risk_approval.lower()
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig

    def test_allows_low_when_min_is_low(self):
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "low"
            result = size_order(self._opp("low"), bankroll=100.0,
                                open_positions=0, daily_pnl=0.0)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig

    def test_unknown_confidence_treated_as_medium(self):
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "medium"
            result = size_order(self._opp("garbage"), bankroll=100.0,
                                open_positions=0, daily_pnl=0.0)
            # Unknown ranks as medium, so medium-floor should approve
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig


# ── R1: NO-side favorite guard + half-Kelly ──────────────────────────────────

class TestNoSideFavoriteGate:
    """Gate 4.6: reject NO bets on heavy favorites unless edge + confidence clear."""

    def _opp(self, side="no", price=0.20, edge=0.30, confidence="high") -> Opportunity:
        return Opportunity(
            ticker="KXMLBGAME-26APR21NYYKAC-NYY",
            title="Test", category="game", side=side,
            market_price=price, fair_value=price + edge, edge=edge,
            edge_source="test", confidence=confidence,
            liquidity_score=8.0, composite_score=8.0, details={},
        )

    def test_no_below_threshold_insufficient_edge_rejected(self):
        # NO at 20¢ (below 25¢ threshold), only 10% edge → rejected
        opp = self._opp(side="no", price=0.20, edge=0.10, confidence="high")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("REJECTED")
        assert "no_side_favorite" in result.risk_approval

    def test_no_below_threshold_low_confidence_rejected(self):
        # NO at 20¢ with 30% edge but medium confidence → still rejected
        # (MIN_CONFIDENCE default=medium would pass gate 4.5, but 4.6 needs high)
        import kalshi_executor
        orig = kalshi_executor.MIN_CONFIDENCE
        try:
            kalshi_executor.MIN_CONFIDENCE = "low"  # disable 4.5 to isolate 4.6
            opp = self._opp(side="no", price=0.20, edge=0.30, confidence="medium")
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("REJECTED")
            assert "no_side_favorite" in result.risk_approval
        finally:
            kalshi_executor.MIN_CONFIDENCE = orig

    def test_no_below_threshold_high_edge_high_conf_approved(self):
        # NO at 20¢ with 30% edge and high confidence → passes the carve-out
        opp = self._opp(side="no", price=0.20, edge=0.30, confidence="high")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("APPROVED")

    def test_no_above_threshold_not_affected(self):
        # NO at 30¢ (above 25¢) is not a "heavy favorite" — gate doesn't apply.
        # Edge 0.10 clears the MLB per-sport floor (0.08) so this isolates 4.6.
        opp = self._opp(side="no", price=0.30, edge=0.10, confidence="medium")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("APPROVED")

    def test_yes_side_not_affected(self):
        # YES at 20¢ (longshot) — gate 4.6 is NO-only. Edge 0.10 clears the
        # MLB per-sport floor (0.08) so the bet isn't rejected for edge first.
        opp = self._opp(side="yes", price=0.20, edge=0.10, confidence="medium")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("APPROVED")


class TestNoSideKellyMultiplier:
    """R1 sizing: NO bets priced below floor get half-Kelly (or configured multiplier)."""

    def _opp(self, side: str, price: float, edge: float = 0.10,
             confidence: str = "high") -> Opportunity:
        return Opportunity(
            ticker="KXMLBGAME-26APR21NYYKAC-NYY",
            title="Test", category="game", side=side,
            market_price=price, fair_value=price + edge, edge=edge,
            edge_source="test", confidence=confidence,
            liquidity_score=8.0, composite_score=8.0, details={},
        )

    def test_no_bet_below_floor_is_halved(self):
        # Same price/edge for YES and NO; NO should size to ~half of YES
        import kalshi_executor
        orig_kelly = kalshi_executor.KELLY_FRACTION
        orig_max = kalshi_executor.MAX_BET_SIZE
        try:
            kalshi_executor.KELLY_FRACTION = 0.50
            kalshi_executor.MAX_BET_SIZE = 10000.0
            # Price 0.30 (below 0.35 floor) with enough edge to scale past flat unit.
            yes_opp = self._opp(side="yes", price=0.30, edge=0.10, confidence="high")
            no_opp = self._opp(side="no", price=0.30, edge=0.10, confidence="high")
            # Need an edge-friendly config where NO gate 4.6 doesn't reject —
            # price 0.30 >= threshold 0.25, so gate 4.6 leaves it alone.
            y = size_order(yes_opp, bankroll=10000.0, open_positions=0,
                           daily_pnl=0.0, unit_size=1.00)
            n = size_order(no_opp, bankroll=10000.0, open_positions=0,
                           daily_pnl=0.0, unit_size=1.00)
            assert y.risk_approval.startswith("APPROVED")
            assert n.risk_approval.startswith("APPROVED")
            # NO contracts should be roughly half of YES contracts (both well
            # above the flat-unit floor so the multiplier actually bites).
            assert n.contracts < y.contracts
            assert n.contracts == pytest.approx(y.contracts // 2, abs=2)
        finally:
            kalshi_executor.KELLY_FRACTION = orig_kelly
            kalshi_executor.MAX_BET_SIZE = orig_max

    def test_no_bet_above_floor_not_halved(self):
        # NO at 40¢ is above the 35¢ floor — same sizing as YES
        import kalshi_executor
        orig_kelly = kalshi_executor.KELLY_FRACTION
        orig_max = kalshi_executor.MAX_BET_SIZE
        try:
            kalshi_executor.KELLY_FRACTION = 0.50
            kalshi_executor.MAX_BET_SIZE = 10000.0
            yes_opp = self._opp(side="yes", price=0.40, edge=0.10, confidence="high")
            no_opp = self._opp(side="no", price=0.40, edge=0.10, confidence="high")
            y = size_order(yes_opp, bankroll=10000.0, open_positions=0,
                           daily_pnl=0.0, unit_size=1.00)
            n = size_order(no_opp, bankroll=10000.0, open_positions=0,
                           daily_pnl=0.0, unit_size=1.00)
            assert y.contracts == n.contracts
        finally:
            kalshi_executor.KELLY_FRACTION = orig_kelly
            kalshi_executor.MAX_BET_SIZE = orig_max

    def test_yes_bet_below_floor_not_halved(self, no_fees):
        # YES at 20¢ should use full Kelly — multiplier is NO-only
        import kalshi_executor
        orig_kelly = kalshi_executor.KELLY_FRACTION
        orig_max = kalshi_executor.MAX_BET_SIZE
        try:
            kalshi_executor.KELLY_FRACTION = 0.50
            kalshi_executor.MAX_BET_SIZE = 10000.0
            yes_low = self._opp(side="yes", price=0.20, edge=0.10, confidence="high")
            yes_high = self._opp(side="yes", price=0.40, edge=0.10, confidence="high")
            low = size_order(yes_low, bankroll=10000.0, open_positions=0,
                             daily_pnl=0.0, unit_size=1.00)
            # Cheaper price → more contracts. Just verify multiplier didn't apply:
            # with multiplier, low-price YES would collapse; without it, it's
            # comfortably above a half-Kelly baseline.
            # We can't compare to YES at 40c directly (different price) but we
            # can confirm sizing scales with the full Kelly shape, not half of it.
            high = size_order(yes_high, bankroll=10000.0, open_positions=0,
                              daily_pnl=0.0, unit_size=1.00)
            # C11: contracts scale as 1 / ((1 - price) * price), so the expected
            # full-Kelly ratio is (1/(0.8*0.2)) / (1/(0.6*0.4)) = 6.25 / 4.167 = 1.5x.
            # (Pre-C11 this was 0.40/0.20 = 2x — the old assertion `>= high * 1.5`
            # survived the change only by 0.5 of a contract, so pin it properly.)
            # A wrongly-applied NO multiplier would halve `low` to 0.75x instead.
            assert low.contracts == pytest.approx(high.contracts * 1.5, rel=0.01)
            assert low.contracts > high.contracts  # and definitively not halved
        finally:
            kalshi_executor.KELLY_FRACTION = orig_kelly
            kalshi_executor.MAX_BET_SIZE = orig_max

    def test_no_bet_multiplier_global_damps_sizing(self):
        # With global multiplier at 0.5, all NO bets are halved regardless of floor
        import kalshi_executor
        orig_kelly = kalshi_executor.KELLY_FRACTION
        orig_max = kalshi_executor.MAX_BET_SIZE
        orig_multiplier_global = kalshi_executor.NO_SIDE_KELLY_MULTIPLIER_GLOBAL
        try:
            kalshi_executor.KELLY_FRACTION = 0.50
            kalshi_executor.MAX_BET_SIZE = 10000.0
            kalshi_executor.NO_SIDE_KELLY_MULTIPLIER_GLOBAL = 0.50
            
            # NO bet at 40¢ is above the price floor (35¢) but should still be halved due to global multiplier
            yes_opp = self._opp(side="yes", price=0.40, edge=0.10, confidence="high")
            no_opp = self._opp(side="no", price=0.40, edge=0.10, confidence="high")
            
            y = size_order(yes_opp, bankroll=10000.0, open_positions=0,
                           daily_pnl=0.0, unit_size=1.00)
            n = size_order(no_opp, bankroll=10000.0, open_positions=0,
                           daily_pnl=0.0, unit_size=1.00)
            
            assert y.risk_approval.startswith("APPROVED")
            assert n.risk_approval.startswith("APPROVED")
            assert n.contracts < y.contracts
            assert n.contracts == pytest.approx(y.contracts // 2, abs=2)
        finally:
            kalshi_executor.KELLY_FRACTION = orig_kelly
            kalshi_executor.MAX_BET_SIZE = orig_max
            kalshi_executor.NO_SIDE_KELLY_MULTIPLIER_GLOBAL = orig_multiplier_global


# ── No-side global edge floor (R28) ──────────────────────────────────────────

class TestNoSideGlobalEdgeFloor:
    """R28: elevated edge floor for all NO bets."""

    def _opp(self, side="no", edge=0.05, sport_ticker="KXMLBGAME-26APR21NYYKAC-NYY") -> Opportunity:
        return Opportunity(
            ticker=sport_ticker,
            title="Test", category="game", side=side,
            market_price=0.30, fair_value=0.30 + edge, edge=edge,
            edge_source="test", confidence="high",
            liquidity_score=8.0, composite_score=8.0, details={},
        )

    def test_no_bet_below_global_no_edge_floor_rejected(self):
        # NO bet at 5% edge is below the 8% global NO floor -> rejected
        import kalshi_executor
        orig_global_no_edge = kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL
        try:
            kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL = 0.08
            opp = self._opp(side="no", edge=0.05)
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("REJECTED")
            assert "edge_below_threshold" in result.risk_approval
        finally:
            kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL = orig_global_no_edge

    def test_no_bet_above_global_no_edge_floor_approved(self):
        # NO bet at 10% edge clears the 8% global NO floor -> approved
        import kalshi_executor
        orig_global_no_edge = kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL
        try:
            kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL = 0.08
            opp = self._opp(side="no", edge=0.10)
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("APPROVED")
        finally:
            kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL = orig_global_no_edge

    def test_yes_bet_below_global_no_edge_floor_approved(self):
        # YES bet at 5% edge is not subject to global NO floor -> approved (since global floor is 3%)
        import kalshi_executor
        orig_global_no_edge = kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL
        try:
            kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL = 0.08
            opp = self._opp(side="yes", edge=0.05)
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("APPROVED")
        finally:
            kalshi_executor.NO_SIDE_MIN_EDGE_GLOBAL = orig_global_no_edge


# ── trusted_edge soft-cap ────────────────────────────────────────────────────

class TestTrustedEdge:
    """Soft-cap on edge used for Kelly sizing."""

    def test_below_cap_is_identity(self):
        assert trusted_edge(0.05, cap=0.15, decay=0.5) == 0.05
        assert trusted_edge(0.10, cap=0.15, decay=0.5) == 0.10

    def test_at_cap_is_identity(self):
        assert trusted_edge(0.15, cap=0.15, decay=0.5) == 0.15

    def test_above_cap_decays(self):
        # 25% edge → 15 + (25-15)*0.5 = 20%
        assert trusted_edge(0.25, cap=0.15, decay=0.5) == pytest.approx(0.20)
        # 35% edge → 15 + (35-15)*0.5 = 25%
        assert trusted_edge(0.35, cap=0.15, decay=0.5) == pytest.approx(0.25)

    def test_monotonic_above_cap(self):
        # Higher raw edge still gives higher trusted edge, just compressed
        assert trusted_edge(0.30, cap=0.15, decay=0.5) > trusted_edge(0.20, cap=0.15, decay=0.5)

    def test_decay_of_zero_hard_caps(self):
        # decay=0 means trusted_edge = cap for anything above it
        assert trusted_edge(0.50, cap=0.15, decay=0.0) == 0.15

    def test_reduces_kelly_contracts_vs_raw_edge(self):
        # An opp with 30% edge should size SMALLER than raw edge would.
        # Pin KELLY_FRACTION and MAX_BET_SIZE so math is independent of local .env.
        import kalshi_executor
        orig_kelly = kalshi_executor.KELLY_FRACTION
        orig_max = kalshi_executor.MAX_BET_SIZE
        orig_floor = kalshi_executor.MIN_MARKET_PRICE
        try:
            kalshi_executor.KELLY_FRACTION = 0.25
            kalshi_executor.MAX_BET_SIZE = 1000.0  # high enough not to cap
            kalshi_executor.MIN_MARKET_PRICE = 0.0  # this test exercises Kelly sizing, not the R7 floor
            opp = Opportunity(
                ticker="KXMLBGAME-99MAR301840CWSMIA-MIA",
                title="Test",
                category="game",
                side="yes",
                market_price=0.10,
                fair_value=0.40,
                edge=0.30,
                edge_source="test",
                confidence="high",
                liquidity_score=8.0,
                composite_score=9.0,
                details={},
            )
            result = size_order(opp, bankroll=400.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            # cap=0.15, decay=0.5 → trusted_edge(0.30) = 0.225
            # C11: Kelly bet = 0.25 * 0.225 * 400 / (1 - 0.10) = $25.00 → 250 contracts at $0.10
            # Raw (untrusted) edge would give 0.25 * 0.30 * 400 / 0.90 = $33.33 → 333 contracts
            assert result.risk_approval == "APPROVED"
            assert result.contracts < 333     # below what raw edge would give
            assert result.contracts >= 200    # but still scales well above flat unit (10)
        finally:
            kalshi_executor.KELLY_FRACTION = orig_kelly
            kalshi_executor.MAX_BET_SIZE = orig_max
            kalshi_executor.MIN_MARKET_PRICE = orig_floor


# ── C11b: floor-aware budget cap ─────────────────────────────────────────────

class TestBudgetCapUnitFloor:
    """C11b (2026-07-27): the budget cap scales proportionally but must not
    shave a bet below its flat unit floor.

    The budget is a fixed pool, so once C11 let favorites size off real Kelly
    they crowded everything else out — on the 07-27 slate an 18c leg fell from
    6 contracts to 2, about a third of its intended size. When even the floors
    don't fit, whole bets are dropped (lowest composite first) instead.
    """

    def _order(self, price, contracts, score=7.0, ticker=None):
        opp = _opp(ticker=ticker or f"KXMLBTOTAL-26JUL27X{int(price * 100)}",
                   price=price, score=score)
        return SizedOrder(
            opportunity=opp, contracts=contracts,
            price_cents=int(price * 100),
            cost_dollars=round(contracts * price, 2),
            bankroll_pct=0.01, risk_approval="APPROVED",
        )

    def test_under_budget_is_untouched(self):
        orders = [self._order(0.80, 3), self._order(0.18, 6)]
        out = _apply_budget_cap(orders, budget=100.0, unit_size=1.00)
        assert [o.contracts for o in out] == [3, 6]

    def test_low_priced_leg_keeps_its_unit_floor(self):
        # Favorites eat the pool; the 18c leg must stay at floor = round(1/0.18) = 6.
        assert unit_size_contracts(0.18, 1.00) == 6
        orders = [self._order(0.83, 10, score=8.0), self._order(0.18, 6, score=6.9)]
        out = _apply_budget_cap(orders, budget=5.00, unit_size=1.00)
        longshot = [o for o in out if o.opportunity.market_price == 0.18][0]
        assert longshot.contracts == 6

    def test_proportional_pass_would_have_undercut_the_floor(self):
        # Same inputs with unit_size=None (pre-C11b behaviour) shave it instead —
        # this is the regression the floor clamp fixes.
        orders = [self._order(0.83, 10, score=8.0), self._order(0.18, 6, score=6.9)]
        out = _apply_budget_cap(orders, budget=5.00, unit_size=None)
        longshot = [o for o in out if o.opportunity.market_price == 0.18][0]
        assert longshot.contracts < 6

    def test_drops_lowest_composite_when_floors_do_not_fit(self):
        # Three legs whose floors alone total $3.00 against a $2.20 budget.
        orders = [
            self._order(0.50, 2, score=9.0, ticker="KXMLBTOTAL-26JUL27-AAA"),
            self._order(0.50, 2, score=8.0, ticker="KXMLBTOTAL-26JUL27-BBB"),
            self._order(0.50, 2, score=5.0, ticker="KXMLBTOTAL-26JUL27-CCC"),
        ]
        out = _apply_budget_cap(orders, budget=2.20, unit_size=1.00)
        kept = {o.opportunity.ticker for o in out}
        assert "KXMLBTOTAL-26JUL27-CCC" not in kept   # weakest dropped
        assert len(out) == 2
        assert sum(o.cost_dollars for o in out) <= 2.20
        # survivors stay whole rather than all three being shaved to 1 contract
        assert all(o.contracts == 2 for o in out)

    def test_never_scales_an_order_up(self):
        # A MAX_BET_SIZE-capped order can sit below its unit floor; the budget
        # cap must not use the floor as an excuse to grow it.
        orders = [self._order(0.10, 3, score=8.0), self._order(0.80, 8, score=7.0)]
        assert unit_size_contracts(0.10, 1.00) == 10   # floor well above 3
        out = _apply_budget_cap(orders, budget=2.00, unit_size=1.00)
        cheap = [o for o in out if o.opportunity.market_price == 0.10][0]
        assert cheap.contracts <= 3

    def test_single_order_honors_budget_over_floor(self):
        orders = [self._order(0.10, 20, score=8.0)]
        out = _apply_budget_cap(orders, budget=0.50, unit_size=1.00)
        assert len(out) == 1
        assert out[0].cost_dollars <= 0.50 + 0.10

    def test_always_lands_within_budget(self):
        for budget in (0.60, 1.10, 2.40, 3.90, 7.50):
            orders = [
                self._order(0.83, 9, score=8.2, ticker="KXMLBTOTAL-26JUL27-A"),
                self._order(0.50, 4, score=7.1, ticker="KXMLBTOTAL-26JUL27-B"),
                self._order(0.18, 6, score=6.5, ticker="KXMLBTOTAL-26JUL27-C"),
            ]
            out = _apply_budget_cap(orders, budget=budget, unit_size=1.00)
            total = sum(o.cost_dollars for o in out)
            assert total <= budget + 0.85, f"budget {budget}: got {total}"
            assert all(o.contracts >= 1 for o in out)

    def test_empty_input(self):
        assert _apply_budget_cap([], budget=10.0, unit_size=1.00) == []


# ── C11: Kelly price-complement divisor ──────────────────────────────────────

class TestKellyPriceComplement:
    """C11 (2026-07-27): Kelly for a binary contract is edge / (1 - price).

    The `/ (1 - price)` term was missing — the even-money approximation, exact
    only at 50c. It under-sized favorites by 1/(1-p) and, because the flat
    UNIT_SIZE floor then won at high prices, pinned essentially every bet above
    ~60c to a single contract.
    """

    def _opp(self, price: float, edge: float = 0.10) -> Opportunity:
        return Opportunity(
            ticker="KXMLBGAME-26APR24-LAD", title="Test", category="game",
            side="yes", market_price=price, fair_value=price + edge, edge=edge,
            edge_source="test", confidence="high",
            liquidity_score=8.0, composite_score=9.0, details={},
        )

    @pytest.fixture(autouse=True)
    def _pin(self, monkeypatch, no_fees):
        import kalshi_executor as ke
        monkeypatch.setattr(ke, "KELLY_FRACTION", 0.50)
        monkeypatch.setattr(ke, "MAX_BET_SIZE", 100000.0)
        monkeypatch.setattr(ke, "MIN_MARKET_PRICE", 0.0)
        monkeypatch.setattr(ke, "_PER_SPORT_MIN_EDGE", {})

    def _contracts(self, price, edge=0.10, bankroll=100000.0):
        r = size_order(self._opp(price, edge), bankroll=bankroll,
                       open_positions=0, daily_pnl=0.0, unit_size=1.00)
        assert r.risk_approval.startswith("APPROVED")
        return r.contracts

    def test_dollars_at_risk_scale_with_one_over_complement(self):
        # At fixed edge, dollars staked scale as 1/(1-p): 80c should draw 5x
        # the dollars of 0c-complement-equivalent... concretely 4x that of 20c
        # ((1/0.2) / (1/0.8) = 4).
        d20 = self._contracts(0.20) * 0.20
        d80 = self._contracts(0.80) * 0.80
        assert d80 / d20 == pytest.approx(4.0, rel=0.02)

    def test_fifty_cent_bet_is_unchanged_by_the_fix(self):
        # 1/(1-0.5) = 2, and the pre-C11 formula is the b=1 special case, so a
        # 50c bet is the one price where old and new agree up to that factor.
        # Pin it as the reference point: $0.50*0.10*100000/0.5 = $10,000 → 20000 ct
        assert self._contracts(0.50) == 20000

    def test_favorite_no_longer_collapses_to_flat_unit(self):
        # The regression this fixes: at a realistic bankroll an 83c bet with a
        # solid edge used to fall back to the flat floor (1 contract).
        # unit_size=1.00 at 83c → flat floor is 1 contract.
        assert unit_size_contracts(0.83, 1.00) == 1
        assert self._contracts(0.83, edge=0.088, bankroll=91.91) > 1

    def test_longshot_sizing_barely_moves(self):
        # The fix is a favorites correction; at 15c the multiplier is only 1.18x,
        # and in practice the flat unit floor dominates there anyway.
        # 0.5*0.10*100/0.85 = $5.88 → 39 contracts at 15c; flat floor is 7.
        assert unit_size_contracts(0.15, 1.00) == 7
        assert self._contracts(0.15, bankroll=100.0) == 39

    def test_extreme_price_does_not_divide_by_zero(self):
        # market_price is clamped upstream, but guard the complement anyway.
        r = size_order(self._opp(0.99, edge=0.005), bankroll=100.0,
                       open_positions=0, daily_pnl=0.0, unit_size=1.00)
        assert r.contracts >= 0
        assert "REJECTED" in r.risk_approval or r.contracts >= 1

    def test_no_side_multiplier_still_composes(self):
        # C11 must not disturb R1/R28 damping: at equal price the NO multiplier
        # is the only difference, so the (1-p) term cancels and NO stays halved.
        import kalshi_executor as ke
        yes = size_order(self._opp(0.40), bankroll=100000.0, open_positions=0,
                         daily_pnl=0.0, unit_size=1.00)
        no_opp = self._opp(0.40)
        no_opp.side = "no"
        with patch.object(ke, "NO_SIDE_KELLY_MULTIPLIER_GLOBAL", 0.50):
            no = size_order(no_opp, bankroll=100000.0, open_positions=0,
                            daily_pnl=0.0, unit_size=1.00)
        assert no.contracts == pytest.approx(yes.contracts // 2, abs=2)


# ── Per-sport MIN_EDGE_THRESHOLD override ─────────────────────────────────────

class TestPerSportMinEdge:
    """Sport-specific edge thresholds via _PER_SPORT_MIN_EDGE."""

    @pytest.fixture(autouse=True)
    def _pin_sizing(self, sizing_defaults):
        """These cases assert gate verdicts, not sizing — see `sizing_defaults`."""

    def _opp(self, ticker: str, edge: float = 0.05) -> Opportunity:
        return Opportunity(
            ticker=ticker,
            title="Test",
            category="game",
            side="yes",
            market_price=0.50,
            fair_value=0.50 + edge,
            edge=edge,
            edge_source="test",
            confidence="high",
            liquidity_score=8.0,
            composite_score=8.0,
            details={},
        )

    def test_min_edge_for_falls_back_to_global(self, no_fees):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            opp = self._opp("KXMLBGAME-99APR171900NYYKAC-NYY")
            assert min_edge_for(opp) == kalshi_executor.MIN_EDGE_THRESHOLD
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_min_edge_for_uses_sport_override(self, no_fees):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            # Control the full dict so the fallback case is independent of
            # whatever per-sport floors .env happens to define.
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.08
            nba_opp = self._opp("KXNBAGAME-26APR02SASLAC-SAS")
            mlb_opp = self._opp("KXMLBGAME-99APR171900NYYKAC-NYY")
            assert min_edge_for(nba_opp) == 0.08
            assert min_edge_for(mlb_opp) == kalshi_executor.MIN_EDGE_THRESHOLD
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_gate_rejects_nba_below_sport_floor(self, no_fees):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.08
            # NBA bet at 5% edge: above global 3% but below NBA 8% → rejected
            nba_opp = self._opp("KXNBAGAME-26APR02SASLAC-SAS", edge=0.05)
            result = size_order(nba_opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("REJECTED")
            assert "edge" in result.risk_approval.lower()
            assert "8.0%" in result.risk_approval  # shows the sport-specific floor
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_gate_approves_other_sports_below_nba_floor(self):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            # Only NBA overridden here; clear first so MLB's real .env floor
            # doesn't bleed in and reject the bet for the wrong reason.
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.08
            # MLB bet at 5% edge: above global 3% → approved (no MLB override)
            mlb_opp = self._opp("KXMLBGAME-99APR171900NYYKAC-NYY", edge=0.05)
            result = size_order(mlb_opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_gate_approves_nba_above_sport_floor(self):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.08
            # NBA bet at 10% edge: above NBA 8% → approved
            nba_opp = self._opp("KXNBAGAME-26APR02SASLAC-SAS", edge=0.10)
            result = size_order(nba_opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)


# ── C5: Series dedup ──────────────────────────────────────────────────────────

class TestMatchupKey:
    """matchup_key() extracts a date-stripped sport+teams signature."""

    def test_same_matchup_different_dates_same_key(self):
        # Real observed bleed pattern: Angels @ Yankees bet Apr 13, 14, 15
        assert matchup_key("KXMLBGAME-26APR13LAAANYY-NYY") == ("mlb", "LAAANYY")
        assert matchup_key("KXMLBGAME-26APR14LAAANYY-NYY") == ("mlb", "LAAANYY")
        assert matchup_key("KXMLBGAME-26APR15LAAANYY-NYY") == ("mlb", "LAAANYY")

    def test_handles_time_suffix(self):
        # Some tickers embed a 4-digit HHMM after the date
        assert matchup_key("KXMLBGAME-26APR011940MINKC-MIN") == ("mlb", "MINKC")

    def test_different_sports_different_keys(self):
        assert matchup_key("KXNBAGAME-26APR02SASLAC-SAS") == ("nba", "SASLAC")
        assert matchup_key("KXNHLGAME-26APR11VGKCOL-VGK") == ("nhl", "VGKCOL")

    def test_returns_none_for_non_game_markets(self):
        # Futures, prediction markets, weather — no sport prefix match
        assert matchup_key("KXBTC-28MAR26-T88000") is None
        assert matchup_key("KXHIGHNY-26APR15-T72") is None

    def test_returns_none_for_malformed(self):
        assert matchup_key("") is None
        assert matchup_key("KXMLBGAME") is None
        assert matchup_key("KXMLBGAME-NODATE-XYZ") is None


class TestRecentMatchupsFromLog:
    """recent_matchups_from_log() builds a set of matchups bet in the window."""

    def _entry(self, ticker: str, hours_ago: float) -> dict:
        ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {"ticker": ticker, "timestamp": ts.isoformat()}

    def test_includes_recent_bets(self):
        log = [
            self._entry("KXMLBGAME-26APR14LAAANYY-NYY", hours_ago=1),
            self._entry("KXNBAGAME-26APR14BOSMIL-BOS", hours_ago=10),
        ]
        result = recent_matchups_from_log(log, hours=48)
        assert ("mlb", "LAAANYY") in result
        assert ("nba", "BOSMIL") in result

    def test_excludes_old_bets(self):
        log = [
            self._entry("KXMLBGAME-26APR14LAAANYY-NYY", hours_ago=100),
        ]
        assert recent_matchups_from_log(log, hours=48) == set()

    def test_zero_hours_disables(self):
        log = [self._entry("KXMLBGAME-26APR14LAAANYY-NYY", hours_ago=0.5)]
        assert recent_matchups_from_log(log, hours=0) == set()

    def test_skips_entries_without_timestamp(self):
        log = [{"ticker": "KXMLBGAME-26APR14LAAANYY-NYY"}]  # no timestamp
        assert recent_matchups_from_log(log, hours=48) == set()

    def test_skips_non_game_tickers(self):
        log = [self._entry("KXBTC-28MAR26-T88000", hours_ago=1)]
        assert recent_matchups_from_log(log, hours=48) == set()


class TestSeriesDedupGate:
    """Gate 7: reject opportunities whose matchup was bet in the window."""

    @pytest.fixture(autouse=True)
    def _pin_sizing(self, sizing_defaults):
        """These cases assert gate verdicts, not sizing — see `sizing_defaults`."""

    def _opp(self, ticker: str) -> Opportunity:
        return Opportunity(
            ticker=ticker, title="Test", category="game", side="yes",
            market_price=0.50, fair_value=0.60, edge=0.10,
            edge_source="test", confidence="high",
            liquidity_score=8.0, composite_score=8.0, details={},
        )

    def test_rejects_when_matchup_in_recent_set(self):
        opp = self._opp("KXMLBGAME-26APR15LAAANYY-NYY")
        recent = {("mlb", "LAAANYY")}
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                            recent_matchups=recent)
        assert result.risk_approval.startswith("REJECTED")
        assert "series_dedup" in result.risk_approval
        assert "LAAANYY" in result.risk_approval

    def test_approves_when_matchup_not_in_set(self):
        opp = self._opp("KXMLBGAME-26APR15LAAANYY-NYY")
        recent = {("mlb", "SOMEOTHERPAIR")}
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                            recent_matchups=recent)
        assert result.risk_approval == "APPROVED"

    def test_approves_when_recent_set_empty(self):
        opp = self._opp("KXMLBGAME-26APR15LAAANYY-NYY")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                            recent_matchups=set())
        assert result.risk_approval == "APPROVED"

    def test_approves_when_recent_set_is_none(self):
        # Backward compat: old callers that don't pass recent_matchups
        opp = self._opp("KXMLBGAME-26APR15LAAANYY-NYY")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval == "APPROVED"

    def test_disabled_when_hours_zero(self):
        # SERIES_DEDUP_HOURS=0 AND no per-sport override → gate fully disabled.
        # Post-R9: must also clear _PER_SPORT_SERIES_DEDUP since per-sport
        # overrides can re-enable the gate independently of the global.
        import kalshi_executor
        orig_global = kalshi_executor.SERIES_DEDUP_HOURS
        orig_per_sport = kalshi_executor._PER_SPORT_SERIES_DEDUP
        try:
            kalshi_executor.SERIES_DEDUP_HOURS = 0
            kalshi_executor._PER_SPORT_SERIES_DEDUP = {}
            opp = self._opp("KXMLBGAME-26APR15LAAANYY-NYY")
            recent = {("mlb", "LAAANYY")}
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                                recent_matchups=recent)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.SERIES_DEDUP_HOURS = orig_global
            kalshi_executor._PER_SPORT_SERIES_DEDUP = orig_per_sport

    def test_non_game_ticker_bypasses_gate(self):
        # Futures/prediction markets have no matchup key — should not be blocked
        opp = self._opp("KXBTC-28MAR26-T88000")
        recent = {("mlb", "LAAANYY")}
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                            recent_matchups=recent)
        assert result.risk_approval == "APPROVED"


# ── R9: Per-sport SERIES_DEDUP_HOURS overrides ──────────────────────────────

class TestPerSportSeriesDedupConstruction:
    """recent_matchups_from_log() uses each sport's specific window when given
    a per_sport_hours map. Motivated by F12 — a 49h NYM/LAD MLB pair slipped
    past the 48h global window and both bets lost."""

    def _entry(self, ticker: str, hours_ago: float) -> dict:
        ts = datetime.now(timezone.utc) - timedelta(hours=hours_ago)
        return {"ticker": ticker, "timestamp": ts.isoformat()}

    def test_mlb_at_49h_caught_with_72h_override(self):
        """The exact F12 case: MLB matchup 49h ago, MLB-specific window 72h."""
        log = [self._entry("KXMLBGAME-26APR14NYMLAD-NYM", hours_ago=49)]
        result = recent_matchups_from_log(
            log, hours=48, per_sport_hours={"mlb": 72}
        )
        assert ("mlb", "NYMLAD") in result

    def test_nba_at_49h_not_caught_when_nba_falls_back_to_48h_global(self):
        """NBA gets no per-sport override → falls back to 48h global → 49h slips."""
        log = [self._entry("KXNBAGAME-26APR14BOSMIL-BOS", hours_ago=49)]
        result = recent_matchups_from_log(
            log, hours=48, per_sport_hours={"mlb": 72}
        )
        assert result == set()

    def test_mlb_at_73h_not_caught_with_72h_override(self):
        """Just past the per-sport window: should NOT be in the recent set."""
        log = [self._entry("KXMLBGAME-26APR14NYMLAD-NYM", hours_ago=73)]
        result = recent_matchups_from_log(
            log, hours=48, per_sport_hours={"mlb": 72}
        )
        assert result == set()

    def test_per_sport_zero_disables_dedup_for_that_sport_only(self):
        """A sport mapped to 0 is opted out even when global is positive."""
        log = [
            self._entry("KXMLBGAME-26APR14NYMLAD-NYM", hours_ago=10),
            self._entry("KXNBAGAME-26APR14BOSMIL-BOS", hours_ago=10),
        ]
        result = recent_matchups_from_log(
            log, hours=48, per_sport_hours={"mlb": 0}
        )
        # MLB disabled → not in set; NBA falls back to global 48h → in set
        assert ("mlb", "NYMLAD") not in result
        assert ("nba", "BOSMIL") in result

    def test_global_zero_with_per_sport_override_still_works(self):
        """User can disable globally but enable per-sport via the override."""
        log = [
            self._entry("KXMLBGAME-26APR14NYMLAD-NYM", hours_ago=10),
            self._entry("KXNBAGAME-26APR14BOSMIL-BOS", hours_ago=10),
        ]
        result = recent_matchups_from_log(
            log, hours=0, per_sport_hours={"mlb": 72}
        )
        # MLB has explicit 72h → in set; NBA inherits the 0 fallback → not in set
        assert ("mlb", "NYMLAD") in result
        assert ("nba", "BOSMIL") not in result

    def test_empty_per_sport_map_preserves_legacy_behavior(self):
        """No per-sport overrides → all sports use the global hours value."""
        log = [
            self._entry("KXMLBGAME-26APR14NYMLAD-NYM", hours_ago=49),
            self._entry("KXMLBGAME-26APR14LAAANYY-NYY", hours_ago=10),
        ]
        result = recent_matchups_from_log(log, hours=48, per_sport_hours={})
        # 49h MLB slips through (legacy bug — exactly what R9 fixes when overrides ARE set)
        assert ("mlb", "NYMLAD") not in result
        assert ("mlb", "LAAANYY") in result


class TestPerSportSeriesDedupGate:
    """size_order() Gate 7 honors the per-sport window in the rejection check
    and reports the actual sport-specific window in the rejection message."""

    @pytest.fixture(autouse=True)
    def _pin_sizing(self, sizing_defaults):
        """These cases assert gate verdicts, not sizing — see `sizing_defaults`."""

    def _opp(self, ticker: str) -> Opportunity:
        return Opportunity(
            ticker=ticker, title="Test", category="game", side="yes",
            market_price=0.50, fair_value=0.60, edge=0.10,
            edge_source="test", confidence="high",
            liquidity_score=8.0, composite_score=8.0, details={},
        )

    def test_mlb_per_sport_hours_appear_in_rejection_message(self):
        """When MLB rejects via per-sport 72h, the message says '72h' not '48h'."""
        import kalshi_executor
        orig = kalshi_executor._PER_SPORT_SERIES_DEDUP
        try:
            kalshi_executor._PER_SPORT_SERIES_DEDUP = {"mlb": 72}
            opp = self._opp("KXMLBGAME-26APR16NYMLAD-NYM")
            recent = {("mlb", "NYMLAD")}
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                                recent_matchups=recent)
            assert result.risk_approval.startswith("REJECTED")
            assert "series_dedup" in result.risk_approval
            assert "72h" in result.risk_approval
        finally:
            kalshi_executor._PER_SPORT_SERIES_DEDUP = orig

    def test_per_sport_zero_disables_gate_for_that_sport(self):
        """If MLB is mapped to 0 in the per-sport dict, MLB matchups bypass the gate."""
        import kalshi_executor
        orig = kalshi_executor._PER_SPORT_SERIES_DEDUP
        try:
            kalshi_executor._PER_SPORT_SERIES_DEDUP = {"mlb": 0}
            opp = self._opp("KXMLBGAME-26APR16NYMLAD-NYM")
            recent = {("mlb", "NYMLAD")}
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                                recent_matchups=recent)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor._PER_SPORT_SERIES_DEDUP = orig

    def test_unmapped_sport_uses_global_window(self):
        """A sport without an override still gets gated by the global window.
        Uses NHL because the test environment may set per-sport edge floors
        for NBA/NCAAB that would short-circuit Gate 3 before Gate 7."""
        import kalshi_executor
        orig_per = kalshi_executor._PER_SPORT_SERIES_DEDUP
        orig_global = kalshi_executor.SERIES_DEDUP_HOURS
        try:
            kalshi_executor._PER_SPORT_SERIES_DEDUP = {"mlb": 72}  # only MLB
            kalshi_executor.SERIES_DEDUP_HOURS = 48
            opp = self._opp("KXNHLGAME-26APR15BOSPHI-BOS")
            recent = {("nhl", "BOSPHI")}
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                                recent_matchups=recent)
            assert result.risk_approval.startswith("REJECTED")
            assert "series_dedup" in result.risk_approval
            assert "48h" in result.risk_approval  # global window used
        finally:
            kalshi_executor._PER_SPORT_SERIES_DEDUP = orig_per
            kalshi_executor.SERIES_DEDUP_HOURS = orig_global


# ── R4: Resting-order janitor ────────────────────────────────────────────────

class FakeKalshiClient:
    """Minimal stub exposing the two methods the janitor uses."""

    def __init__(self, orders: list[dict], cancel_error_on: set[str] | None = None,
                 list_raises: Exception | None = None):
        self._orders = orders
        self._cancel_error_on = cancel_error_on or set()
        self._list_raises = list_raises
        self.cancelled_ids: list[str] = []
        self.cancelled_shards: list[int | None] = []

    def get_orders(self, status=None, limit=100, cursor=None, ticker=None):
        if self._list_raises is not None:
            raise self._list_raises
        return {"orders": self._orders}

    def cancel_order(self, order_id: str, exchange_index: int | None = None):
        if order_id in self._cancel_error_on:
            raise KalshiAPIError(500, "cancel failed")
        self.cancelled_ids.append(order_id)
        self.cancelled_shards.append(exchange_index)
        return {"order_id": order_id, "status": "canceled"}


def _order(order_id: str, hours_ago: float, fill_count: int = 0,
           ticker: str = "KXMLB-TEST", created: str | None = None,
           now: "datetime | None" = None) -> dict:
    now = now or datetime.now(timezone.utc)
    ts = now - timedelta(hours=hours_ago)
    return {
        "order_id": order_id,
        "ticker": ticker,
        "status": "resting",
        "fill_count_fp": str(fill_count),
        "remaining_count_fp": "10",
        "created_time": created if created is not None else ts.isoformat(),
    }


class TestRestingOrderJanitor:
    """R4: cancel_stale_resting_orders() cleans up old zero-fill orders."""

    def test_cancels_stale_zero_fill_orders(self):
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient([
            _order("old-1", hours_ago=30, now=now),
            _order("old-2", hours_ago=40, now=now),
        ])
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert len(result) == 2
        assert set(client.cancelled_ids) == {"old-1", "old-2"}
        assert all(r["age_hours"] >= 24 for r in result)

    def test_forwards_the_orders_shard_to_cancel(self):
        """Post-sharding (2026-08-24), a cancel without `exchange_index`
        resolves against shard 0 and returns a bare 404 for an MLB/tennis
        order -- which reads exactly like "already gone", so the janitor would
        report a clean sweep while the order kept resting. Proven live on
        2026-08-27: cancelling order 01a043b2 on KXMLBGAME failed until
        `?exchange_index=3` was added.
        """
        now = datetime.now(timezone.utc)
        mlb = _order("mlb-1", hours_ago=30, ticker="KXMLBGAME-TEST", now=now)
        mlb["exchange_index"] = 3
        client = FakeKalshiClient([mlb, _order("nfl-1", hours_ago=30, now=now)])

        cancel_stale_resting_orders(client, max_hours=24, now=now)

        assert client.cancelled_ids == ["mlb-1", "nfl-1"]
        # shard 3 forwarded; the shardless order passes None and defaults to 0
        assert client.cancelled_shards == [3, None]

    def test_skips_young_orders(self):
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient([
            _order("young-1", hours_ago=5, now=now),
            _order("young-2", hours_ago=23.5, now=now),
        ])
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert result == []
        assert client.cancelled_ids == []

    def test_skips_partial_or_filled_orders(self):
        # Old but has fills — still an active position, let the settler handle it
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient([
            _order("partial", hours_ago=48, fill_count=5, now=now),
            _order("filled", hours_ago=100, fill_count=10, now=now),
        ])
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert result == []
        assert client.cancelled_ids == []

    def test_mixed_batch_cancels_only_stale_zero_fill(self):
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient([
            _order("old-empty", hours_ago=30, fill_count=0, now=now),
            _order("old-partial", hours_ago=30, fill_count=3, now=now),
            _order("young-empty", hours_ago=5, fill_count=0, now=now),
        ])
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert len(result) == 1
        assert result[0]["order_id"] == "old-empty"
        assert client.cancelled_ids == ["old-empty"]

    def test_zero_hours_disables_janitor(self):
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient([
            _order("old-1", hours_ago=999, now=now),
        ])
        result = cancel_stale_resting_orders(client, max_hours=0, now=now)
        assert result == []
        assert client.cancelled_ids == []

    def test_negative_hours_disables_janitor(self):
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient([_order("old-1", hours_ago=999, now=now)])
        assert cancel_stale_resting_orders(client, max_hours=-1, now=now) == []

    def test_list_api_error_returns_empty_no_crash(self):
        client = FakeKalshiClient([], list_raises=KalshiAPIError(500, "API down"))
        result = cancel_stale_resting_orders(client, max_hours=24)
        assert result == []

    def test_cancel_api_error_skips_that_order_continues_batch(self):
        now = datetime.now(timezone.utc)
        client = FakeKalshiClient(
            [
                _order("good", hours_ago=30, now=now),
                _order("bad", hours_ago=30, now=now),
            ],
            cancel_error_on={"bad"},
        )
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        # "good" cancelled; "bad" logged but not in the result list
        assert [r["order_id"] for r in result] == ["good"]
        assert client.cancelled_ids == ["good"]

    def test_missing_timestamp_skipped(self):
        now = datetime.now(timezone.utc)
        orders = [_order("old-1", hours_ago=30, now=now)]
        orders[0]["created_time"] = None  # malformed
        client = FakeKalshiClient(orders)
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert result == []

    def test_malformed_timestamp_skipped(self):
        now = datetime.now(timezone.utc)
        orders = [_order("bad-ts", hours_ago=30, now=now)]
        orders[0]["created_time"] = "not-a-date"
        client = FakeKalshiClient(orders)
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert result == []

    def test_naive_timestamp_treated_as_utc(self):
        now = datetime.now(timezone.utc)
        stale_naive = (now - timedelta(hours=30)).replace(tzinfo=None).isoformat()
        orders = [_order("naive", hours_ago=30, now=now)]
        orders[0]["created_time"] = stale_naive
        client = FakeKalshiClient(orders)
        result = cancel_stale_resting_orders(client, max_hours=24, now=now)
        assert len(result) == 1
        assert client.cancelled_ids == ["naive"]

    def test_default_max_hours_from_env(self):
        # When max_hours is None, use the module-level RESTING_ORDER_MAX_HOURS
        import kalshi_executor
        orig = kalshi_executor.RESTING_ORDER_MAX_HOURS
        try:
            kalshi_executor.RESTING_ORDER_MAX_HOURS = 24
            now = datetime.now(timezone.utc)
            client = FakeKalshiClient([
                _order("old", hours_ago=30, now=now),
                _order("young", hours_ago=5, now=now),
            ])
            result = cancel_stale_resting_orders(client, max_hours=None, now=now)
            assert len(result) == 1
            assert client.cancelled_ids == ["old"]
        finally:
            kalshi_executor.RESTING_ORDER_MAX_HOURS = orig


# ── dedup_correlated_brackets ────────────────────────────────────────────────

def _dedup_opp(ticker: str, category: str, score: float) -> Opportunity:
    """Minimal Opportunity fixture for dedup tests — only the fields that matter."""
    return Opportunity(
        ticker=ticker,
        title=ticker,
        category=category,
        side="yes",
        market_price=0.50,
        fair_value=0.60,
        edge=0.10,
        edge_source="test",
        confidence="medium",
        liquidity_score=5.0,
        composite_score=score,
        details={},
    )


class TestDedupCorrelatedBrackets:
    """Regression tests for dedup_correlated_brackets.

    Alt-line brackets on the same game SHOULD collapse (correlated).
    Futures outcomes (each team in a championship) should NOT collapse —
    fixed 2026-04-24 after a futures scan of 20 opps was deduping to 2.
    """

    def test_alt_lines_same_game_same_category_collapse_to_best(self):
        # Three Over lines on the same NBA game — all correlated
        opps = [
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-207", "total", score=6.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.5),  # best
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-210", "total", score=7.2),
        ]
        result = dedup_correlated_brackets(opps)
        assert len(result) == 1
        assert result[0].ticker == "KXNBATOTAL-26APR24SASPOR-208"

    def test_different_categories_same_game_both_kept(self):
        # ML and Total on the same game are different categories, both kept
        opps = [
            _dedup_opp("KXNBAGAME-26APR24SASPOR-SAS", "game", score=7.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.0),
        ]
        result = dedup_correlated_brackets(opps)
        assert len(result) == 2

    def test_futures_outcomes_all_pass_through(self):
        # 3 different teams in NBA Finals — each is a distinct bet, must NOT collapse
        opps = [
            _dedup_opp("KXNBA-26-LAL", "futures", score=6.5),
            _dedup_opp("KXNBA-26-BOS", "futures", score=7.2),
            _dedup_opp("KXNBA-26-OKC", "futures", score=8.0),
        ]
        result = dedup_correlated_brackets(opps)
        assert len(result) == 3
        tickers = {o.ticker for o in result}
        assert tickers == {"KXNBA-26-LAL", "KXNBA-26-BOS", "KXNBA-26-OKC"}

    def test_futures_and_games_dont_interfere(self):
        opps = [
            _dedup_opp("KXNBAGAME-26APR24SASPOR-SAS", "game", score=7.0),
            _dedup_opp("KXNBA-26-LAL", "futures", score=6.5),
            _dedup_opp("KXNBA-26-BOS", "futures", score=7.2),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-207", "total", score=6.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.5),  # best total
        ]
        result = dedup_correlated_brackets(opps)
        # 1 game + 2 futures + 1 total (best of the two) = 4
        assert len(result) == 4

    def test_preserves_input_order_by_composite(self):
        # Input sorted by score descending; output should preserve that order
        opps = [
            _dedup_opp("KXNBA-26-OKC", "futures", score=9.0),
            _dedup_opp("KXNBA-26-BOS", "futures", score=7.0),
            _dedup_opp("KXNBA-26-LAL", "futures", score=5.0),
        ]
        result = dedup_correlated_brackets(opps)
        assert [o.ticker for o in result] == ["KXNBA-26-OKC", "KXNBA-26-BOS", "KXNBA-26-LAL"]

    # ── R8: cross-category dedup ────────────────────────────────────────────

    def test_cross_category_off_keeps_categories_separate(self):
        """Default (no opt-in) preserves pre-R8 behavior: ML+Total+Spread on
        the same game survive as 3 distinct bets. Regression guard."""
        opps = [
            _dedup_opp("KXNBAGAME-26APR24SASPOR-SAS", "game", score=7.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.0),
            _dedup_opp("KXNBASPREAD-26APR24SASPOR-7", "spread", score=6.5),
        ]
        # Both no-arg and explicit-empty-set must behave identically
        assert len(dedup_correlated_brackets(opps)) == 3
        assert len(dedup_correlated_brackets(opps, cross_category_sports=set())) == 3

    def test_cross_category_on_collapses_categories(self):
        """When sport opted in, all categories on the same game collapse to
        the highest-composite bet."""
        opps = [
            _dedup_opp("KXNBAGAME-26APR24SASPOR-SAS", "game", score=7.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.5),  # best
            _dedup_opp("KXNBASPREAD-26APR24SASPOR-7", "spread", score=6.5),
        ]
        result = dedup_correlated_brackets(opps, cross_category_sports={"nba"})
        assert len(result) == 1
        assert result[0].ticker == "KXNBATOTAL-26APR24SASPOR-208"

    def test_cross_category_per_sport_scope(self):
        """Opting in NBA must not collapse MLB. Different games on the same
        sport also stay independent (event_key still distinguishes games)."""
        opps = [
            # Same NBA game across 3 categories — collapses to 1
            _dedup_opp("KXNBAGAME-26APR24SASPOR-SAS", "game", score=7.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.5),  # best NBA
            _dedup_opp("KXNBASPREAD-26APR24SASPOR-7", "spread", score=6.5),
            # Same MLB game across 2 categories — both kept (MLB not opted in)
            _dedup_opp("KXMLBGAME-26APR24LADNYM-LAD", "game", score=7.5),
            _dedup_opp("KXMLBTOTAL-26APR24LADNYM-8.5", "total", score=8.0),
            # Different NBA game — its own collapse group, unaffected
            _dedup_opp("KXNBAGAME-26APR24LALDEN-LAL", "game", score=6.0),
        ]
        result = dedup_correlated_brackets(opps, cross_category_sports={"nba"})
        tickers = {o.ticker for o in result}
        assert tickers == {
            "KXNBATOTAL-26APR24SASPOR-208",  # best of the SAS/POR collapse
            "KXMLBGAME-26APR24LADNYM-LAD",
            "KXMLBTOTAL-26APR24LADNYM-8.5",
            "KXNBAGAME-26APR24LALDEN-LAL",
        }
        assert len(result) == 4

    def test_cross_category_does_not_affect_futures(self):
        """Even when NBA is opted in, futures outcomes (each team distinct)
        must still pass through — same-sport but they're not bracket bets."""
        opps = [
            _dedup_opp("KXNBA-26-LAL", "futures", score=6.5),
            _dedup_opp("KXNBA-26-BOS", "futures", score=7.2),
            _dedup_opp("KXNBA-26-OKC", "futures", score=8.0),
            # Plus one regular NBA game with two categories — should collapse
            _dedup_opp("KXNBAGAME-26APR24SASPOR-SAS", "game", score=7.0),
            _dedup_opp("KXNBATOTAL-26APR24SASPOR-208", "total", score=8.5),
        ]
        result = dedup_correlated_brackets(opps, cross_category_sports={"nba"})
        # 3 futures (untouched) + 1 collapsed game = 4
        assert len(result) == 4
        tickers = {o.ticker for o in result}
        assert {"KXNBA-26-LAL", "KXNBA-26-BOS", "KXNBA-26-OKC"} <= tickers
        assert "KXNBATOTAL-26APR24SASPOR-208" in tickers


# ── preflight_gate_status (R18) ──────────────────────────────────────────────

def _opp(ticker="KXMLBGAME-26APR24-LAD", side="yes", price=0.50, edge=0.10,
         confidence="medium", score=7.0, category="game") -> Opportunity:
    """Build an Opportunity fixture with defaults that pass every static gate."""
    return Opportunity(
        ticker=ticker,
        title=ticker,
        category=category,
        side=side,
        market_price=price,
        fair_value=price + edge,
        edge=edge,
        edge_source="test",
        confidence=confidence,
        liquidity_score=5.0,
        composite_score=score,
        details={},
    )


class TestPreflightGateStatus:
    """R18 (2026-04-24): `preflight_gate_status` must predict the same reject
    verdict size_order reaches, using only static per-opportunity properties.
    Runtime gates (daily loss, position count, dupe ticker, per-event cap,
    series dedup) are NOT covered — those need portfolio/log state.
    """

    def test_ok_when_all_static_gates_pass(self):
        assert preflight_gate_status(_opp()) == "ok"

    def test_flags_edge_gate(self):
        # NBA ticker + 0.05 edge is below the live 0.12 NBA floor
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.12
            opp = _opp(ticker="KXNBAGAME-26APR24BOSPHI-BOS", edge=0.05)
            assert preflight_gate_status(opp) == "edge"
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_flags_price_gate(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "MIN_MARKET_PRICE", 0.10)
        opp = _opp(price=0.08)
        assert preflight_gate_status(opp) == "price"

    def test_flags_score_gate(self, monkeypatch):
        # This is the user-observed case (composite 4.6 on LAD futures)
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "MIN_COMPOSITE_SCORE", 6.0)
        opp = _opp(score=4.6)
        assert preflight_gate_status(opp) == "score"

    def test_flags_confidence_gate(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "MIN_CONFIDENCE", "medium")
        opp = _opp(confidence="low")
        assert preflight_gate_status(opp) == "conf"

    def test_flags_no_favorite_gate_when_edge_insufficient(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "NO_SIDE_FAVORITE_THRESHOLD", 0.25)
        monkeypatch.setattr(kalshi_executor, "NO_SIDE_MIN_EDGE", 0.25)
        # NO + market below threshold + edge 10% + medium confidence → rejected
        opp = _opp(side="no", price=0.15, edge=0.10, confidence="medium")
        assert preflight_gate_status(opp) == "no-fav"

    def test_no_favorite_passes_with_high_conf_and_big_edge(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "NO_SIDE_FAVORITE_THRESHOLD", 0.25)
        monkeypatch.setattr(kalshi_executor, "NO_SIDE_MIN_EDGE", 0.25)
        # The R1 carve-out: edge >= 25% AND confidence = high → allowed
        opp = _opp(side="no", price=0.15, edge=0.30, confidence="high", score=9.0)
        assert preflight_gate_status(opp) == "ok"

    def test_yes_side_never_hits_no_favorite_gate(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "NO_SIDE_FAVORITE_THRESHOLD", 0.25)
        # YES + same low price should NOT trigger the NO-favorite gate
        opp = _opp(side="yes", price=0.15, edge=0.10, confidence="medium", score=7.0)
        assert preflight_gate_status(opp) == "ok"

    def test_first_failing_gate_wins(self, monkeypatch):
        # If both score and confidence fail, check we return the earlier gate
        # in size_order's sequence (score is gate 4, conf is gate 4.5)
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "MIN_COMPOSITE_SCORE", 6.0)
        monkeypatch.setattr(kalshi_executor, "MIN_CONFIDENCE", "medium")
        opp = _opp(score=4.6, confidence="low")
        assert preflight_gate_status(opp) == "score"

    def test_flags_prediction_gate_when_disabled(self, monkeypatch):
        # R25 Gate 4.7: crypto/weather/spx/mentions/companies/politics
        # categories are blocked by default
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_PREDICTION_BETS", False)
        for cat in ("crypto", "weather", "spx", "mentions", "companies", "politics"):
            opp = _opp(category=cat, score=9.0, edge=0.20, confidence="high")
            assert preflight_gate_status(opp) == "pred-off", f"{cat} should be blocked"

    def test_prediction_gate_opens_with_env_flag(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_PREDICTION_BETS", True)
        opp = _opp(category="crypto", score=9.0, edge=0.20, confidence="high")
        assert preflight_gate_status(opp) == "ok"

    def test_prediction_gate_does_not_affect_sports(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_PREDICTION_BETS", False)
        # Sports categories should be untouched regardless of the flag
        for cat in ("game", "spread", "total", "futures", "player_prop"):
            opp = _opp(category=cat, score=9.0)
            assert preflight_gate_status(opp) == "ok", f"{cat} should not be blocked"

    def test_size_order_rejects_crypto_when_flag_off(self, monkeypatch):
        # End-to-end: Gate 4.7 actually rejects through size_order, not just
        # the preflight helper
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_PREDICTION_BETS", False)
        opp = _opp(category="crypto", ticker="KXBTC-26MAY01-B80000",
                   score=9.0, edge=0.20, confidence="high")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("REJECTED")
        assert "prediction_market_disabled" in result.risk_approval
        assert "crypto" in result.risk_approval

    # ── L1 Gate 4.8: live/in-play safety gate ────────────────────────────────
    # A ticker with an embedded *past* start time is an in-progress game.
    STARTED_TICKER = "KXMLBGAME-20JUN011840CWSMIA-MIA"   # Jun 1 2020 — long started
    UPCOMING_TICKER = "KXMLBGAME-99JUN011840CWSMIA-MIA"  # Jun 1 2099 — pre-game

    def test_flags_live_gate_when_disabled(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_LIVE_BETS", False)
        opp = _opp(ticker=self.STARTED_TICKER, score=9.0, edge=0.20,
                   confidence="high")
        assert preflight_gate_status(opp) == "live-off"

    def test_live_gate_opens_with_flag(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_LIVE_BETS", True)
        opp = _opp(ticker=self.STARTED_TICKER, score=9.0, edge=0.20,
                   confidence="high")
        assert preflight_gate_status(opp) == "ok"

    def test_live_gate_ignores_pregame(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_LIVE_BETS", False)
        opp = _opp(ticker=self.UPCOMING_TICKER, score=9.0, edge=0.20,
                   confidence="high")
        assert preflight_gate_status(opp) == "ok"

    def test_size_order_rejects_live_when_flag_off(self, monkeypatch):
        import kalshi_executor
        monkeypatch.setattr(kalshi_executor, "ALLOW_LIVE_BETS", False)
        opp = _opp(ticker=self.STARTED_TICKER, score=9.0, edge=0.20,
                   confidence="high")
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.risk_approval.startswith("REJECTED")
        assert "live_betting_disabled" in result.risk_approval


class TestReloadRiskConfig:
    """Config-reload seam (2026-06-14): a long-running host snapshots the
    risk-gate globals at import and would keep stale gates after a `.env`
    edit until restarted — silently approving
    sub-floor bets. `reload_risk_config()` re-reads config into the module
    globals on demand. The CLI (fresh process per run) and the monkey-patch
    seam used by every other test here are deliberately untouched.
    """

    # Every config-derived module global reload_risk_config() refreshes.
    _NAMES = (
        "MAX_BET_SIZE", "UNIT_SIZE", "MAX_DAILY_LOSS", "MAX_OPEN_POSITIONS",
        "MIN_EDGE_THRESHOLD", "KELLY_FRACTION", "MAX_PER_EVENT", "MAX_BET_RATIO",
        "MIN_COMPOSITE_SCORE", "KELLY_EDGE_CAP", "KELLY_EDGE_DECAY",
        "SERIES_DEDUP_HOURS", "MIN_MARKET_PRICE", "RESTING_ORDER_MAX_HOURS",
        "MIN_CONFIDENCE", "NO_SIDE_FAVORITE_THRESHOLD", "NO_SIDE_MIN_EDGE",
        "NO_SIDE_KELLY_PRICE_FLOOR", "NO_SIDE_KELLY_MULTIPLIER",
        "ALLOW_PREDICTION_BETS", "CROSS_CATEGORY_DEDUP",
        "_PER_SPORT_MIN_EDGE", "_PER_SPORT_SERIES_DEDUP",
        "_PER_SPORT_CROSS_CATEGORY_DEDUP",
    )

    def _snapshot(self, ke):
        snap = {n: getattr(ke, n) for n in self._NAMES}
        # Copy the mutable per-sport dicts so restore is independent.
        for n in ("_PER_SPORT_MIN_EDGE", "_PER_SPORT_SERIES_DEDUP",
                  "_PER_SPORT_CROSS_CATEGORY_DEDUP"):
            snap[n] = dict(snap[n])
        return snap

    def _restore(self, ke, snap):
        from app.config import reset_config
        for name, value in snap.items():
            setattr(ke, name, value)
        reset_config()  # drop the memoized Config primed from the simulated env

    def test_reload_picks_up_env_edits(self, monkeypatch):
        import kalshi_executor as ke
        # Don't let the real .env file override the simulated edits.
        monkeypatch.setattr(ke, "load_dotenv", lambda *a, **k: None)
        snap = self._snapshot(ke)
        try:
            monkeypatch.setenv("MIN_MARKET_PRICE", "0.20")
            monkeypatch.setenv("MIN_EDGE_THRESHOLD_MLB", "0.09")
            monkeypatch.setenv("MIN_CONFIDENCE", "high")
            ke.reload_risk_config()
            assert ke.MIN_MARKET_PRICE == 0.20
            assert ke._PER_SPORT_MIN_EDGE.get("mlb") == 0.09
            assert ke.MIN_CONFIDENCE == "high"
        finally:
            self._restore(ke, snap)

    def test_reload_idempotent_without_edits(self, monkeypatch):
        import kalshi_executor as ke
        monkeypatch.setattr(ke, "load_dotenv", lambda *a, **k: None)
        snap = self._snapshot(ke)
        try:
            before = ke.MIN_MARKET_PRICE
            ke.reload_risk_config()
            assert ke.MIN_MARKET_PRICE == before
        finally:
            self._restore(ke, snap)

    def test_reload_raised_floor_rejects_cheap_bet(self, monkeypatch):
        # End-to-end: the bug we fixed. A $0.05 bet that would clear a low floor
        # is rejected by size_order once reload picks up a raised MIN_MARKET_PRICE.
        import kalshi_executor as ke
        monkeypatch.setattr(ke, "load_dotenv", lambda *a, **k: None)
        snap = self._snapshot(ke)
        try:
            monkeypatch.setenv("MIN_MARKET_PRICE", "0.25")
            ke.reload_risk_config()
            opp = _opp(price=0.05, edge=0.50, confidence="high", score=9.0)
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
            assert result.risk_approval.startswith("REJECTED")
            assert "price_below_floor" in result.risk_approval
            assert result.contracts == 0
        finally:
            self._restore(ke, snap)


# ── PM2c: venue minimum-order size ───────────────────────────────────────────

class TestVenueMinShares:
    """PM2c: `size_order` bumps counts up to a venue's per-order share minimum
    (`opp.details["min_order_shares"]`, recorded by the Polymarket US scanner)
    or rejects when the bump would breach MAX_BET_SIZE / bankroll. Opps without
    the details key (all Kalshi opps) are untouched."""

    @pytest.fixture(autouse=True)
    def _pin_kelly(self, monkeypatch):
        """Pin KELLY_FRACTION to the code default (0.25).

        These cases exercise the venue min-share bump, not Kelly, and are
        written for the regime where flat unit sizing wins at a $20 bankroll.
        `kalshi_executor.KELLY_FRACTION` is a module global sourced from the
        operator's live `.env`, so without this the class silently retunes
        itself to whatever the bankroll experiment of the day is set to — it
        broke on 2026-07-22 when KELLY_FRACTION went 0.25 -> 1 and Kelly
        started clearing the unit floor."""
        import kalshi_executor as ke
        monkeypatch.setattr(ke, "KELLY_FRACTION", 0.25)

    def _pm_opp(self, price=0.50, min_shares=5, **kw):
        opp = _opp(ticker="PM-tec-nba-champ-2027-sas", price=price, **kw)
        opp.details["venue"] = "polymarket"
        opp.details["min_order_shares"] = min_shares
        return opp

    def test_bumps_to_venue_minimum(self):
        # $0.50 x $1 unit → 2 contracts (quarter-Kelly at $20 bankroll gives
        # only 1), below the 5-share minimum → bumped.
        result = size_order(self._pm_opp(), bankroll=20.0, open_positions=0,
                            daily_pnl=0.0, unit_size=1.00)
        assert result.risk_approval == "APPROVED_BUMPED_MIN_SHARES"
        assert result.contracts == 5
        assert result.cost_dollars == 2.50

    def test_no_bump_when_already_at_minimum(self):
        # Flat sizing already reaches the 2-share minimum → normal approval.
        result = size_order(self._pm_opp(min_shares=2), bankroll=20.0,
                            open_positions=0, daily_pnl=0.0, unit_size=1.00)
        assert result.risk_approval == "APPROVED"
        assert result.contracts == 2

    def test_rejects_when_bump_exceeds_bankroll(self):
        result = size_order(self._pm_opp(), bankroll=2.00, open_positions=0,
                            daily_pnl=0.0, unit_size=1.00)
        assert result.risk_approval.startswith("REJECTED")
        assert "below_venue_min_shares" in result.risk_approval
        assert result.contracts == 0

    def test_rejects_when_max_bet_cap_undercuts_minimum(self):
        # Kelly at $100 bankroll sizes 5 shares ($2.50); a $2.00 MAX_BET_SIZE
        # caps that to 4 — below the 5-share minimum, and re-bumping would
        # breach the cap → reject (the check runs AFTER the caps).
        import kalshi_executor as ke
        original = ke.MAX_BET_SIZE
        try:
            ke.MAX_BET_SIZE = 2.00
            result = size_order(self._pm_opp(), bankroll=100.0,
                                open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert "below_venue_min_shares" in result.risk_approval
        finally:
            ke.MAX_BET_SIZE = original

    def test_kalshi_opp_without_details_key_unaffected(self):
        result = size_order(_opp(), bankroll=20.0, open_positions=0,
                            daily_pnl=0.0, unit_size=1.00)
        assert result.risk_approval == "APPROVED"
        assert result.contracts == 2  # flat $1 unit at $0.50 — no bump


class TestLiquidityGate:
    """Gate 3.6: reject markets whose book is too wide or too dead to trade.

    CLAUDE.md has listed "the market is clearly illiquid (spread > 5%)" as a
    Hard Stop since launch, and MLB_FILTERING_GUIDE.md repeats it as a
    graduated rule, but neither was ever enforced -- spread reached scoring
    only through the soft `liquidity` composite term. The 2026-08-18 NFL
    Week 1 audit found 13 of 27 open positions past the documented line (up
    to 20c wide) and 18 of 27 with zero 24h volume.
    """

    def _opp(self, spread=None, volume=None) -> Opportunity:
        details = {}
        if spread is not None:
            details["bid_ask_spread"] = spread
        if volume is not None:
            details["volume_24h"] = volume
        return Opportunity(
            ticker="KXNFLTOTAL-26SEP13CLEJAC-20",
            title="Will there be over 19.5 points scored?",
            category="total",
            side="yes",
            market_price=0.80,
            fair_value=0.95,
            edge=0.15,
            edge_source="test",
            confidence="high",
            liquidity_score=6.0,
            composite_score=8.5,
            details=details,
        )

    def _size(self, opp):
        return size_order(opp, bankroll=500.0, open_positions=0,
                          daily_pnl=0.0, unit_size=1.00)

    def test_rejects_wide_book(self):
        # The real CLEJAC-20 book: bid 0.77 / ask 0.97.
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            result = self._size(self._opp(spread=0.20))
            assert result.risk_approval.startswith("REJECTED")
            assert "illiquid_spread" in result.risk_approval
            assert result.contracts == 0
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig

    def test_allows_spread_exactly_at_limit(self):
        # Documented rule is "spread > 5%", so 5c itself passes.
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            assert "illiquid" not in self._size(self._opp(spread=0.05)).risk_approval
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig

    def test_allows_tight_book(self):
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            assert "illiquid" not in self._size(self._opp(spread=0.02)).risk_approval
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig

    def test_zero_disables_spread_check(self):
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.0
            assert "illiquid" not in self._size(self._opp(spread=0.40)).risk_approval
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig

    def test_rejects_dead_book_when_volume_floor_set(self):
        # Tolerable 4c spread, but nothing has traded in 24h.
        import kalshi_executor
        orig_s = kalshi_executor.MAX_BID_ASK_SPREAD
        orig_v = kalshi_executor.MIN_MARKET_VOLUME_24H
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            kalshi_executor.MIN_MARKET_VOLUME_24H = 50
            result = self._size(self._opp(spread=0.04, volume=0))
            assert "illiquid_volume" in result.risk_approval
            assert result.contracts == 0
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig_s
            kalshi_executor.MIN_MARKET_VOLUME_24H = orig_v

    def test_volume_floor_off_by_default(self):
        import kalshi_executor
        orig_v = kalshi_executor.MIN_MARKET_VOLUME_24H
        try:
            kalshi_executor.MIN_MARKET_VOLUME_24H = 0
            assert "illiquid" not in self._size(self._opp(spread=0.02, volume=0)).risk_approval
        finally:
            kalshi_executor.MIN_MARKET_VOLUME_24H = orig_v

    def test_fails_open_when_microstructure_missing(self):
        # A hand-built Opportunity or replayed scan cache carries no spread.
        # Unknown must not mean rejected, or non-sports paths would be blocked
        # wholesale.
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            assert "illiquid" not in self._size(self._opp()).risk_approval
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig

    def test_garbage_spread_does_not_crash(self):
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            assert "illiquid" not in self._size(self._opp(spread="n/a")).risk_approval
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig

    def test_preflight_reports_illiq(self):
        import kalshi_executor
        orig = kalshi_executor.MAX_BID_ASK_SPREAD
        try:
            kalshi_executor.MAX_BID_ASK_SPREAD = 0.05
            assert kalshi_executor.preflight_gate_status(self._opp(spread=0.20)) == "illiq"
            assert kalshi_executor.preflight_gate_status(self._opp(spread=0.02)) == "ok"
        finally:
            kalshi_executor.MAX_BID_ASK_SPREAD = orig
