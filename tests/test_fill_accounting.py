"""Tests for fill-based trade accounting (X5).

Validates that the trade journal, settler, and risk check use *filled*
values rather than *requested* values, so resting and partially-filled
orders don't overstate exposure or distort P&L.
"""

import pytest
from trade_log import get_filled_contracts, get_filled_cost
from kalshi_executor import log_trade, SizedOrder
from opportunity import Opportunity


# ── Helpers ──────────────────────────────────────────────────────────────────

def _make_opp(price=0.50, edge=0.10):
    return Opportunity(
        ticker="KXNBAGAME-26APR04BOSNYK-BOS",
        title="BOS vs NYK Winner?",
        category="game",
        side="yes",
        market_price=price,
        fair_value=price + edge,
        edge=edge,
        edge_source="test",
        confidence="high",
        liquidity_score=8.0,
        composite_score=8.5,
        details={},
    )


def _make_sized(opp, contracts=10, price_cents=50, cost=5.00):
    return SizedOrder(
        opportunity=opp,
        contracts=contracts,
        price_cents=price_cents,
        cost_dollars=cost,
        bankroll_pct=0.05,
        risk_approval="APPROVED",
    )


def _make_api_response(fill_count=10, remaining=0, status="executed"):
    """Simulate a Kalshi create_order API response."""
    return {
        "order": {
            "order_id": "ord-test-123",
            "status": status,
            "fill_count_fp": str(fill_count),
            "remaining_count_fp": str(remaining),
            "taker_fees_dollars": "0.05",
            "maker_fees_dollars": "0",
        }
    }


# ── get_filled_contracts / get_filled_cost helpers ────────────────────────

class TestGetFilledContracts:
    def test_new_format_uses_filled_contracts(self):
        trade = {"filled_contracts": 7, "contracts": 10, "fill_count": "7"}
        assert get_filled_contracts(trade) == 7

    def test_old_format_uses_fill_count(self):
        trade = {"contracts": 10, "fill_count": "7"}
        assert get_filled_contracts(trade) == 7

    def test_old_format_zero_fill_count_falls_back(self):
        """Old records with fill_count=0 fall back to contracts (legacy)."""
        trade = {"contracts": 10, "fill_count": "0"}
        assert get_filled_contracts(trade) == 10

    def test_legacy_no_fill_count(self):
        """Very old records with no fill_count at all."""
        trade = {"contracts": 10}
        assert get_filled_contracts(trade) == 10

    def test_empty_fill_count_string(self):
        trade = {"contracts": 5, "fill_count": ""}
        assert get_filled_contracts(trade) == 5


class TestGetFilledCost:
    def test_new_format(self):
        trade = {"filled_cost": 3.50, "cost_dollars": 5.00}
        assert get_filled_cost(trade) == 3.50

    def test_old_format_derives_from_fill_count(self):
        trade = {"cost_dollars": 5.00, "fill_count": "7", "market_price_at_entry": 0.50}
        assert get_filled_cost(trade) == 3.50

    def test_old_format_zero_fill_falls_back(self):
        trade = {"cost_dollars": 5.00, "fill_count": "0", "market_price_at_entry": 0.50}
        assert get_filled_cost(trade) == 5.00

    def test_legacy_no_fill_count(self):
        trade = {"cost_dollars": 5.00}
        assert get_filled_cost(trade) == 5.00


# ── log_trade fill scenarios ─────────────────────────────────────────────

class TestLogTradeFillScenarios:
    def test_fully_filled_order(self):
        opp = _make_opp()
        sized = _make_sized(opp, contracts=10, cost=5.00)
        api = _make_api_response(fill_count=10, remaining=0, status="executed")
        trade_log = []

        record = log_trade(api, sized, trade_log)

        assert record["requested_contracts"] == 10
        assert record["requested_cost"] == 5.00
        assert record["filled_contracts"] == 10
        assert record["filled_cost"] == 5.00
        assert record["contracts"] == 10  # legacy field matches filled
        assert record["cost_dollars"] == 5.00
        assert record["fill_status"] == "filled"

    def test_partial_fill_order(self):
        opp = _make_opp()
        sized = _make_sized(opp, contracts=10, cost=5.00)
        api = _make_api_response(fill_count=3, remaining=7, status="resting")
        trade_log = []

        record = log_trade(api, sized, trade_log)

        assert record["requested_contracts"] == 10
        assert record["requested_cost"] == 5.00
        assert record["filled_contracts"] == 3
        assert record["filled_cost"] == 1.50  # 3 * 0.50
        assert record["contracts"] == 3
        assert record["cost_dollars"] == 1.50
        assert record["fill_status"] == "partial"

    def test_zero_fill_resting_order(self):
        opp = _make_opp()
        sized = _make_sized(opp, contracts=10, cost=5.00)
        api = _make_api_response(fill_count=0, remaining=10, status="resting")
        trade_log = []

        record = log_trade(api, sized, trade_log)

        assert record["requested_contracts"] == 10
        assert record["requested_cost"] == 5.00
        assert record["filled_contracts"] == 0
        assert record["filled_cost"] == 0.0
        assert record["contracts"] == 0
        assert record["cost_dollars"] == 0.0
        assert record["fill_status"] == "resting"

    def test_resting_order_not_counted_as_exposure(self):
        """A resting order should contribute $0 to wagered totals."""
        record = {
            "filled_contracts": 0,
            "filled_cost": 0.0,
            "requested_contracts": 10,
            "requested_cost": 5.00,
            "fill_status": "resting",
        }
        assert get_filled_cost(record) == 0.0
        assert get_filled_contracts(record) == 0

    def test_partial_fill_exposure_matches_filled_not_requested(self):
        """A partially filled order should show only filled exposure."""
        record = {
            "filled_contracts": 3,
            "filled_cost": 1.50,
            "requested_contracts": 10,
            "requested_cost": 5.00,
            "fill_status": "partial",
        }
        assert get_filled_cost(record) == 1.50
        assert get_filled_contracts(record) == 3


# ── Settlement with fill-based accounting ─────────────────────────────────

class TestSettlementAccounting:
    def test_pnl_uses_filled_cost(self):
        """Settlement should compute P&L from filled cost, not requested."""
        from kalshi_settler import calculate_pnl

        trade = {
            "side": "yes",
            "filled_contracts": 3,
            "filled_cost": 1.50,
            "requested_contracts": 10,
            "requested_cost": 5.00,
            "contracts": 3,
            "cost_dollars": 1.50,
            "taker_fees": "0.03",
            "maker_fees": "0",
        }
        settlement = {"market_result": "yes", "revenue": 0}

        pnl = calculate_pnl(trade, settlement)

        # Won: 3 contracts * $1.00 = $3.00 revenue
        # Cost: $1.50 (filled, not $5.00 requested)
        # Fees: $0.03
        assert pnl["revenue"] == 3.00
        assert pnl["cost"] == 1.50
        assert pnl["net_pnl"] == pytest.approx(3.00 - 1.50 - 0.03, abs=0.01)
        assert pnl["won"] is True

    def test_pnl_zero_fill_no_pnl(self):
        """A resting order that settles should have zero P&L."""
        from kalshi_settler import calculate_pnl

        trade = {
            "side": "yes",
            "filled_contracts": 0,
            "filled_cost": 0.0,
            "contracts": 0,
            "cost_dollars": 0.0,
            "taker_fees": "0",
            "maker_fees": "0",
        }
        settlement = {"market_result": "yes", "revenue": 0}

        pnl = calculate_pnl(trade, settlement)

        assert pnl["revenue"] == 0.0
        assert pnl["cost"] == 0.0
        assert pnl["net_pnl"] == 0.0
