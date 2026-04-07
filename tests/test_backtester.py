"""Tests for the backtesting framework (W1)."""

import pytest
from backtest.backtester import (
    BacktestResult, filter_trades, _equity_curve, _max_drawdown,
    _sharpe_ratio, _streaks, _breakdown, _edge_bucket_breakdown,
    _calibration_curve, _category_from_ticker, simulate_strategies,
    generate_markdown,
)


def _make_trade(**overrides):
    """Create a minimal trade dict for testing."""
    base = {
        "trade_id": "test-001",
        "ticker": "KXNBAGAME-26APR01LALBOS-LAL",
        "side": "yes",
        "result": "yes",
        "won": True,
        "contracts": 5,
        "cost": 2.50,
        "revenue": 5.00,
        "fees": 0.05,
        "net_pnl": 2.45,
        "roi": 0.98,
        "edge_estimated": 0.10,
        "fair_value": 0.60,
        "market_price_at_entry": 0.50,
        "confidence": "medium",
        "settled_at": "2026-04-01T12:00:00Z",
        "sport": "NBA",
        "category": "game",
    }
    base.update(overrides)
    return base


SAMPLE_TRADES = [
    _make_trade(trade_id="1", won=True, net_pnl=2.00, cost=1.00, edge_estimated=0.08,
                fair_value=0.58, confidence="medium", settled_at="2026-04-01T10:00:00Z",
                category="game", sport="NBA"),
    _make_trade(trade_id="2", won=False, net_pnl=-1.00, cost=1.00, edge_estimated=0.12,
                fair_value=0.62, confidence="high", settled_at="2026-04-01T12:00:00Z",
                category="spread", sport="NCAAB"),
    _make_trade(trade_id="3", won=True, net_pnl=1.50, cost=1.00, edge_estimated=0.06,
                fair_value=0.56, confidence="medium", settled_at="2026-04-02T10:00:00Z",
                category="total", sport="MLB"),
    _make_trade(trade_id="4", won=False, net_pnl=-0.50, cost=0.50, edge_estimated=0.20,
                fair_value=0.70, confidence="high", settled_at="2026-04-02T12:00:00Z",
                category="game", sport="NBA"),
    _make_trade(trade_id="5", won=True, net_pnl=3.00, cost=2.00, edge_estimated=0.15,
                fair_value=0.65, confidence="medium", settled_at="2026-04-03T10:00:00Z",
                category="total", sport="MLB"),
]


class TestCategoryFromTicker:
    def test_game(self):
        assert _category_from_ticker("KXNBAGAME-26APR01LALBOS-LAL") == "game"

    def test_spread(self):
        assert _category_from_ticker("KXNCAAMBSPREAD-26MAR22UCLACONN-UCLA8") == "spread"

    def test_total(self):
        assert _category_from_ticker("KXNBATOTAL-26APR07UTANOP-236") == "total"

    def test_other(self):
        assert _category_from_ticker("KXSOMETHING-UNKNOWN") == "other"


class TestFilterTrades:
    def test_filter_by_sport(self):
        result = filter_trades(SAMPLE_TRADES, sport="mlb")
        assert len(result) == 2
        assert all(t["sport"] == "MLB" for t in result)

    def test_filter_by_confidence(self):
        result = filter_trades(SAMPLE_TRADES, confidence="high")
        assert len(result) == 2

    def test_filter_by_category(self):
        result = filter_trades(SAMPLE_TRADES, category="total")
        assert len(result) == 2

    def test_filter_by_min_edge(self):
        result = filter_trades(SAMPLE_TRADES, min_edge=0.10)
        assert len(result) == 3

    def test_filter_by_after(self):
        result = filter_trades(SAMPLE_TRADES, after="2026-04-02")
        assert len(result) == 3

    def test_combined_filters(self):
        result = filter_trades(SAMPLE_TRADES, sport="nba", confidence="medium")
        assert len(result) == 1


class TestEquityCurve:
    def test_cumulative_pnl(self):
        curve = _equity_curve(SAMPLE_TRADES)
        assert len(curve) == 5
        assert curve[0]["cumulative"] == 2.00
        assert curve[1]["cumulative"] == 1.00  # 2.00 + (-1.00)
        assert curve[-1]["cumulative"] == 5.00  # total

    def test_empty(self):
        assert _equity_curve([]) == []


class TestMaxDrawdown:
    def test_with_drawdown(self):
        curve = _equity_curve(SAMPLE_TRADES)
        dd, dd_pct = _max_drawdown(curve)
        assert dd == 1.0  # peak 2.00, trough 1.00
        assert dd_pct == 0.5

    def test_no_drawdown(self):
        trades = [
            _make_trade(net_pnl=1.0, cost=1.0, settled_at="2026-04-01T10:00:00Z"),
            _make_trade(net_pnl=2.0, cost=1.0, settled_at="2026-04-02T10:00:00Z"),
        ]
        dd, dd_pct = _max_drawdown(_equity_curve(trades))
        assert dd == 0.0

    def test_empty(self):
        assert _max_drawdown([]) == (0.0, 0.0)


class TestSharpeRatio:
    def test_positive_sharpe(self):
        sharpe = _sharpe_ratio(SAMPLE_TRADES)
        assert sharpe > 0

    def test_single_trade(self):
        assert _sharpe_ratio([SAMPLE_TRADES[0]]) == 0.0

    def test_empty(self):
        assert _sharpe_ratio([]) == 0.0


class TestStreaks:
    def test_streaks(self):
        max_win, max_lose = _streaks(SAMPLE_TRADES)
        # W, L, W, L, W -> max_win=1, max_lose=1
        assert max_win == 1
        assert max_lose == 1

    def test_all_wins(self):
        trades = [_make_trade(won=True)] * 5
        assert _streaks(trades) == (5, 0)

    def test_all_losses(self):
        trades = [_make_trade(won=False)] * 3
        assert _streaks(trades) == (0, 3)


class TestBreakdown:
    def test_by_sport(self):
        result = _breakdown(SAMPLE_TRADES, "sport")
        assert "NBA" in result
        assert "MLB" in result
        assert result["MLB"]["trades"] == 2
        assert result["MLB"]["wins"] == 2

    def test_by_confidence(self):
        result = _breakdown(SAMPLE_TRADES, "confidence")
        assert result["medium"]["win_rate"] == 1.0
        assert result["high"]["win_rate"] == 0.0


class TestEdgeBucketBreakdown:
    def test_buckets(self):
        result = _edge_bucket_breakdown(SAMPLE_TRADES)
        assert "5-10%" in result
        assert "10-15%" in result
        assert "15-25%" in result

    def test_avg_edge_present(self):
        result = _edge_bucket_breakdown(SAMPLE_TRADES)
        for bucket, stats in result.items():
            assert "avg_edge" in stats
            assert stats["avg_edge"] > 0


class TestCalibrationCurve:
    def test_buckets(self):
        result = _calibration_curve(SAMPLE_TRADES)
        assert len(result) > 0
        for row in result:
            assert "bucket" in row
            assert "avg_predicted" in row
            assert "actual_win_rate" in row
            assert "gap" in row


class TestBacktestResult:
    def test_full_analysis(self):
        result = BacktestResult(trades=SAMPLE_TRADES, label="Test").analyze()
        assert result.total_trades == 5
        assert result.wins == 3
        assert result.losses == 2
        assert result.win_rate == 0.6
        assert result.net_pnl == 5.0
        assert result.roi > 0
        assert result.profit_factor > 1
        assert len(result.equity_curve) == 5
        assert len(result.by_sport) > 0
        assert len(result.by_category) > 0
        assert len(result.calibration) > 0

    def test_empty(self):
        result = BacktestResult(trades=[], label="Empty").analyze()
        assert result.total_trades == 0
        assert result.net_pnl == 0


class TestSimulateStrategies:
    def test_returns_multiple(self):
        results = simulate_strategies(SAMPLE_TRADES)
        assert len(results) >= 1
        assert results[0].label == "Baseline (all trades)"

    def test_all_analyzed(self):
        results = simulate_strategies(SAMPLE_TRADES)
        for r in results:
            assert r.total_trades > 0


class TestMarkdownReport:
    def test_generates_content(self):
        result = BacktestResult(trades=SAMPLE_TRADES, label="Test").analyze()
        md = generate_markdown(result)
        assert "# Edge-Radar Backtest Report" in md
        assert "Summary" in md
        assert "By Sport" in md
        assert "Calibration" in md

    def test_with_strategies(self):
        result = BacktestResult(trades=SAMPLE_TRADES, label="Test").analyze()
        strategies = simulate_strategies(SAMPLE_TRADES)
        md = generate_markdown(result, strategies)
        assert "Strategy Simulation" in md
