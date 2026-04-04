"""Tests for risk gates and position sizing in kalshi_executor.py.

These protect real money — every rejection path must work correctly.
"""

import os
import pytest
from unittest.mock import patch

from opportunity import Opportunity
from kalshi_executor import unit_size_contracts, size_order, SizedOrder


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
                              "MIN_EDGE_THRESHOLD": "0.03", "MIN_COMPOSITE_SCORE": "6.0",
                              "MIN_CONFIDENCE": "low"})
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

    @patch.dict(os.environ, {"MIN_CONFIDENCE": "high"})
    def test_rejected_low_confidence(self):
        opp = self._make_opp(confidence="low")
        result = size_order(opp, bankroll=100.0, open_positions=5, daily_pnl=0.0)
        assert result.risk_approval != "APPROVED"
        assert "confidence" in result.risk_approval.lower()

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

    def test_approved_capped_concentration(self):
        # Tiny bankroll forces concentration cap
        import kalshi_executor
        orig = kalshi_executor.MAX_CONCENTRATION
        try:
            kalshi_executor.MAX_CONCENTRATION = 0.05  # 5%
            opp = self._make_opp(price=0.10, edge=0.50, score=9.0)
            result = size_order(opp, bankroll=10.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED_CAPPED_CONCENTRATION"
            assert result.cost_dollars <= 10.0 * 0.05 + 0.11  # within concentration limit
        finally:
            kalshi_executor.MAX_CONCENTRATION = orig

    def test_approved_capped_max_bet(self):
        # Big Kelly bet hits the sports max bet cap
        import kalshi_executor
        orig_sports = kalshi_executor.MAX_BET_SIZE_SPORTS
        orig_conc = kalshi_executor.MAX_CONCENTRATION
        try:
            kalshi_executor.MAX_BET_SIZE_SPORTS = 5.0  # low cap
            kalshi_executor.MAX_CONCENTRATION = 1.0  # disable concentration cap
            opp = self._make_opp(price=0.10, edge=0.50, score=9.0)
            result = size_order(opp, bankroll=500.0, open_positions=0, daily_pnl=0.0, unit_size=1.00)
            assert result.risk_approval == "APPROVED_CAPPED_MAX_BET"
            assert result.cost_dollars <= 5.0 + 0.11
        finally:
            kalshi_executor.MAX_BET_SIZE_SPORTS = orig_sports
            kalshi_executor.MAX_CONCENTRATION = orig_conc
