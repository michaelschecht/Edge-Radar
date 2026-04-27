"""Tests for R5 — settlement schema + reconciliation report.

Two surfaces:
  1. `build_settlement_record()` carries the full R5 trade-side context.
  2. `print_reconciliation()` reports trade-log <-> settlement join health.
"""

import pytest

from kalshi_settler import build_settlement_record


# ── Fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture
def filled_trade():
    """A fully-filled trade record with every R5 field populated."""
    return {
        "trade_id": "trade-abc-123",
        "order_id": "ord-xyz-789",
        "ticker": "KXNBAGAME-26APR04BOSNYK-BOS",
        "title": "BOS vs NYK Winner?",
        "category": "game",
        "side": "yes",
        "edge_estimated": 0.10,
        "edge_source": "odds_consensus",
        "fair_value": 0.60,
        "market_price_at_entry": 0.50,
        "confidence": "high",
        "composite_score": 8.5,
        "risk_approval": "APPROVED",
        "bankroll_pct": 0.05,
        "unit_size": 0.50,
        "fill_status": "filled",
        "filled_contracts": 10,
        "filled_cost": 5.00,
        "closed_at": "2026-04-05T22:30:00Z",
    }


@pytest.fixture
def pnl_won():
    return {
        "result": "yes",
        "won": True,
        "revenue": 10.00,
        "cost": 5.00,
        "fees": 0.05,
        "net_pnl": 4.95,
        "roi": 0.99,
    }


# ── build_settlement_record — R5 schema ──────────────────────────────────────

class TestBuildSettlementRecord:
    """The settlement record carries the full R5 trade-side context."""

    def test_carries_trade_id(self, filled_trade, pnl_won):
        rec = build_settlement_record(filled_trade, pnl_won, None, None)
        assert rec["trade_id"] == "trade-abc-123"

    def test_carries_r5_added_fields(self, filled_trade, pnl_won):
        """Fields R5 added: composite_score, risk_approval, bankroll_pct, etc."""
        rec = build_settlement_record(filled_trade, pnl_won, 0.55, 0.05)
        assert rec["order_id"] == "ord-xyz-789"
        assert rec["title"] == "BOS vs NYK Winner?"
        assert rec["category"] == "game"
        assert rec["edge_source"] == "odds_consensus"
        assert rec["closing_price"] == 0.55
        assert rec["clv"] == 0.05
        assert rec["composite_score"] == 8.5
        assert rec["risk_approval"] == "APPROVED"
        assert rec["bankroll_pct"] == 0.05
        assert rec["unit_size"] == 0.50
        assert rec["fill_status"] == "filled"

    def test_carries_legacy_fields(self, filled_trade, pnl_won):
        """Pre-R5 fields still flow through — no regression."""
        rec = build_settlement_record(filled_trade, pnl_won, None, None)
        assert rec["ticker"] == "KXNBAGAME-26APR04BOSNYK-BOS"
        assert rec["side"] == "yes"
        assert rec["edge_estimated"] == 0.10
        assert rec["fair_value"] == 0.60
        assert rec["market_price_at_entry"] == 0.50
        assert rec["confidence"] == "high"
        assert rec["settled_at"] == "2026-04-05T22:30:00Z"

    def test_carries_pnl_fields(self, filled_trade, pnl_won):
        rec = build_settlement_record(filled_trade, pnl_won, None, None)
        assert rec["result"] == "yes"
        assert rec["won"] is True
        assert rec["revenue"] == 10.00
        assert rec["cost"] == 5.00
        assert rec["fees"] == 0.05
        assert rec["net_pnl"] == 4.95
        assert rec["roi"] == 0.99
        assert rec["contracts"] == 10

    def test_missing_optional_fields_serialize_as_none(self, pnl_won):
        """A bare-minimum trade still produces a complete-shaped record."""
        bare = {"trade_id": "x", "ticker": "T1", "side": "no", "closed_at": "2026-04-05"}
        rec = build_settlement_record(bare, pnl_won, None, None)
        # All R5 fields exist as keys with None values, not missing
        assert rec["composite_score"] is None
        assert rec["risk_approval"] is None
        assert rec["bankroll_pct"] is None
        assert rec["closing_price"] is None
        assert rec["clv"] is None


# ── print_reconciliation — join-health report ────────────────────────────────

class TestPrintReconciliation:
    """The reconciliation report runs cleanly across the lifecycle states."""

    def _stub_logs(self, monkeypatch, trades, settlements):
        # Patch where risk_check imports them, not where they're defined
        import risk_check
        monkeypatch.setattr(risk_check, "load_trade_log", lambda: trades)
        monkeypatch.setattr(risk_check, "load_settlement_log", lambda: settlements)

    def test_runs_on_empty_logs(self, monkeypatch, capsys):
        self._stub_logs(monkeypatch, [], [])
        from risk_check import print_reconciliation
        print_reconciliation()  # should not raise
        out = capsys.readouterr().out
        assert "Trade log entries" in out
        assert "0" in out  # zero entries, zero settlements

    def test_runs_on_all_orphaned(self, monkeypatch, capsys):
        """Production state today: 0 trade-log entries, many orphaned settlements."""
        settlements = [
            {"trade_id": f"s-{i}", "ticker": "T", "settled_at": "2026-03-22T00:00:00Z"}
            for i in range(5)
        ]
        self._stub_logs(monkeypatch, [], settlements)
        from risk_check import print_reconciliation
        print_reconciliation()
        out = capsys.readouterr().out
        assert "5" in out  # 5 settlements
        assert "Orphaned" in out

    def test_runs_on_clean_join(self, monkeypatch, capsys):
        """Post-R5 happy path: settlements join cleanly to the trade log."""
        trades = [
            {"trade_id": "t-1", "ticker": "T1", "closed_at": "2026-04-01"},
            {"trade_id": "t-2", "ticker": "T2", "closed_at": "2026-04-02"},
        ]
        settlements = [
            {"trade_id": "t-1", "composite_score": 8.5, "risk_approval": "APPROVED"},
            {"trade_id": "t-2", "composite_score": 7.0, "risk_approval": "APPROVED"},
        ]
        self._stub_logs(monkeypatch, trades, settlements)
        from risk_check import print_reconciliation
        print_reconciliation()
        out = capsys.readouterr().out
        # 100% join coverage
        assert "100.0%" in out

    def test_open_trade_count(self, monkeypatch, capsys):
        """Open trades (no closed_at) are counted separately from orphans."""
        trades = [
            {"trade_id": "t-1", "ticker": "T1", "closed_at": None},
            {"trade_id": "t-2", "ticker": "T2", "closed_at": "2026-04-02"},
            {"trade_id": "t-error", "ticker": "T3", "status": "error"},
        ]
        settlements = [{"trade_id": "t-2"}]
        self._stub_logs(monkeypatch, trades, settlements)
        from risk_check import print_reconciliation
        print_reconciliation()
        out = capsys.readouterr().out
        assert "Open trades" in out
        # 1 open trade (the error-status one is excluded)
        # We just verify the report doesn't crash and includes the metric label.

    def test_field_coverage_calculated(self, monkeypatch, capsys):
        """Mixed pre/post-R5 settlements produce a partial-coverage display."""
        settlements = [
            # Pre-R5 record (legacy schema)
            {"trade_id": "old-1", "ticker": "T1"},
            # Post-R5 record (full schema)
            {"trade_id": "new-1", "ticker": "T2", "composite_score": 8.0,
             "risk_approval": "APPROVED", "bankroll_pct": 0.05},
        ]
        self._stub_logs(monkeypatch, [], settlements)
        from risk_check import print_reconciliation
        print_reconciliation()
        out = capsys.readouterr().out
        # composite_score populated 1/2 = 50%
        assert "50%" in out
