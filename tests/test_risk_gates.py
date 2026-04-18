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
)


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

    def _make_opp(self, edge=0.10, confidence="high", score=8.0, price=0.50):
        return Opportunity(
            ticker="KXMLBGAME-26MAR301840CWSMIA-MIA",
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
        # Very cheap price with tiny bankroll
        opp = self._make_opp(price=0.02, edge=0.10, score=8.0)
        result = size_order(opp, bankroll=0.05, open_positions=0, daily_pnl=0.0, unit_size=1.00)
        # Should not size more than bankroll allows
        assert result.cost_dollars <= 0.05 + 0.01  # small float tolerance

    def test_price_clamped_to_valid_range(self):
        # Price at extreme low
        opp = self._make_opp(price=0.005, edge=0.10, score=8.0)
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0)
        assert result.price_cents >= 1

    def test_approved_clean_when_no_caps_hit(self):
        # Small bet, big bankroll — no caps triggered
        opp = self._make_opp(price=0.50, edge=0.05, score=8.0)
        result = size_order(opp, bankroll=500.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
        assert result.risk_approval == "APPROVED"

    def test_approved_capped_max_bet(self):
        # Big Kelly bet hits the max bet cap
        import kalshi_executor
        orig_max = kalshi_executor.MAX_BET_SIZE
        try:
            kalshi_executor.MAX_BET_SIZE = 5.0  # low cap
            opp = self._make_opp(price=0.10, edge=0.50, score=9.0)
            result = size_order(opp, bankroll=500.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED_CAPPED_MAX_BET"
            assert result.cost_dollars <= 5.0 + 0.11
        finally:
            kalshi_executor.MAX_BET_SIZE = orig_max


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
        try:
            kalshi_executor.KELLY_FRACTION = 0.25
            kalshi_executor.MAX_BET_SIZE = 1000.0  # high enough not to cap
            opp = Opportunity(
                ticker="KXMLBGAME-26MAR301840CWSMIA-MIA",
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
            # Kelly bet = 0.25 * 0.225 * 400 = $22.50 → 225 contracts at $0.10
            # Raw Kelly would be 0.25 * 0.30 * 400 = $30 → 300 contracts
            assert result.risk_approval == "APPROVED"
            assert result.contracts < 300     # below what raw edge would give
            assert result.contracts >= 200    # but still scales well above flat unit (10)
        finally:
            kalshi_executor.KELLY_FRACTION = orig_kelly
            kalshi_executor.MAX_BET_SIZE = orig_max


# ── Per-sport MIN_EDGE_THRESHOLD override ─────────────────────────────────────

class TestPerSportMinEdge:
    """Sport-specific edge thresholds via _PER_SPORT_MIN_EDGE."""

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

    def test_min_edge_for_falls_back_to_global(self):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            opp = self._opp("KXMLBGAME-26APR171900NYYKAC-NYY")
            assert min_edge_for(opp) == kalshi_executor.MIN_EDGE_THRESHOLD
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_min_edge_for_uses_sport_override(self):
        import kalshi_executor
        orig = dict(kalshi_executor._PER_SPORT_MIN_EDGE)
        try:
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.08
            nba_opp = self._opp("KXNBAGAME-26APR02SASLAC-SAS")
            mlb_opp = self._opp("KXMLBGAME-26APR171900NYYKAC-NYY")
            assert min_edge_for(nba_opp) == 0.08
            assert min_edge_for(mlb_opp) == kalshi_executor.MIN_EDGE_THRESHOLD
        finally:
            kalshi_executor._PER_SPORT_MIN_EDGE.clear()
            kalshi_executor._PER_SPORT_MIN_EDGE.update(orig)

    def test_gate_rejects_nba_below_sport_floor(self):
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
            kalshi_executor._PER_SPORT_MIN_EDGE["nba"] = 0.08
            # MLB bet at 5% edge: above global 3% → approved (no MLB override)
            mlb_opp = self._opp("KXMLBGAME-26APR171900NYYKAC-NYY", edge=0.05)
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
        # SERIES_DEDUP_HOURS=0 should bypass the gate even with entries in the set
        import kalshi_executor
        orig = kalshi_executor.SERIES_DEDUP_HOURS
        try:
            kalshi_executor.SERIES_DEDUP_HOURS = 0
            opp = self._opp("KXMLBGAME-26APR15LAAANYY-NYY")
            recent = {("mlb", "LAAANYY")}
            result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                                recent_matchups=recent)
            assert result.risk_approval == "APPROVED"
        finally:
            kalshi_executor.SERIES_DEDUP_HOURS = orig

    def test_non_game_ticker_bypasses_gate(self):
        # Futures/prediction markets have no matchup key — should not be blocked
        opp = self._opp("KXBTC-28MAR26-T88000")
        recent = {("mlb", "LAAANYY")}
        result = size_order(opp, bankroll=100.0, open_positions=0, daily_pnl=0.0,
                            recent_matchups=recent)
        assert result.risk_approval == "APPROVED"
