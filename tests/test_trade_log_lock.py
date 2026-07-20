"""Tests for the cross-process trade-log lock and merge-safe append (M2).

The `_isolate_data_logs` autouse fixture in conftest redirects TRADE_LOG_PATH /
SETTLEMENT_LOG_PATH to a per-test tmp dir, so every write here is hermetic and
the lock file lands in tmp too (via `trade_log._lock_path`).
"""

import trade_log
from trade_log import (
    append_trades,
    load_trade_log,
    save_trade_log,
    save_settlement_log,
    trade_log_lock,
)


class TestTradeLogLock:
    def test_lock_path_follows_patched_log_path(self):
        # conftest patched TRADE_LOG_PATH to a tmp dir; the lock must live beside it
        assert trade_log._lock_path() == trade_log.TRADE_LOG_PATH.parent / ".trade_log.lock"

    def test_lock_is_a_working_context_manager(self):
        with trade_log_lock(timeout=5):
            save_trade_log([{"trade_id": "X"}])
        assert load_trade_log()[0]["trade_id"] == "X"

    def test_noop_fallback_when_filelock_missing(self, monkeypatch):
        # Simulate filelock being unavailable: the context must still yield and
        # writes must still happen (atomic-write-only, no lock).
        monkeypatch.setattr(trade_log, "_HAVE_FILELOCK", False)
        monkeypatch.setattr(trade_log, "_warned_no_filelock", False, raising=False)
        with trade_log_lock():
            save_trade_log([{"trade_id": "Y"}])
        assert load_trade_log()[0]["trade_id"] == "Y"


class TestAppendTrades:
    def test_append_adds_records(self):
        save_trade_log([{"trade_id": "A"}])
        append_trades([{"trade_id": "B"}, {"trade_id": "C"}])
        ids = [t["trade_id"] for t in load_trade_log()]
        assert ids == ["A", "B", "C"]

    def test_append_empty_is_noop(self):
        save_trade_log([{"trade_id": "A"}])
        append_trades([])
        assert [t["trade_id"] for t in load_trade_log()] == ["A"]

    def test_append_preserves_records_written_after_caller_loaded(self):
        # The lost-update scenario: caller loads a stale snapshot, another
        # process appends B to disk, then the caller appends C. B must survive.
        save_trade_log([{"trade_id": "A"}])
        load_trade_log()  # caller takes a stale snapshot: [A]

        # concurrent writer (e.g. the settler) appends B directly to disk
        save_trade_log([{"trade_id": "A"}, {"trade_id": "B"}])

        # caller, still holding the stale [A], appends C — must NOT clobber B
        append_trades([{"trade_id": "C"}])

        ids = {t["trade_id"] for t in load_trade_log()}
        assert ids == {"A", "B", "C"}


class TestSettlerConcurrencySafety:
    """End-to-end: a trade an executor appends while the settler is doing its
    Kalshi network fetch (Phase 1) must survive the settler's save (Phase 2)."""

    @staticmethod
    def _trade(tid, ticker="T-A"):
        return {
            "trade_id": tid,
            "order_id": "o" + tid,
            "ticker": ticker,
            "side": "yes",
            "status": "filled",
            "fill_status": "filled",
            "closed_at": None,
            "filled_contracts": 4,
            "filled_cost": 1.6,
            "market_price_at_entry": 0.40,
            "taker_fees": "0",
            "maker_fees": "0",
            "fair_value": 0.5,
            "edge_estimated": 0.1,
        }

    class _FakeClient:
        def __init__(self, on_network):
            self._on_network = on_network
            self._fired = False

        def get_settlements(self, limit=200, cursor=None):
            # simulate a concurrent executor opening a position mid-fetch
            if not self._fired:
                self._on_network()
                self._fired = True
            return {
                "settlements": [{
                    "ticker": "T-A",
                    "market_result": "yes",
                    "revenue": 400,  # cents
                    "settled_time": "2026-07-20T00:00:00Z",
                }],
                "cursor": "",
            }

        def get_market(self, ticker):
            return {"market": {
                "status": "settled",
                "result": "yes",
                "last_price": 55,
                "close_time": "2026-07-20T00:00:00Z",
            }}

    def test_concurrent_append_during_fetch_is_not_clobbered(self):
        import kalshi_settler

        save_trade_log([self._trade("A")])
        save_settlement_log([])

        def concurrent_executor_append():
            append_trades([self._trade("CONCURRENT", ticker="T-NEW")])

        client = self._FakeClient(concurrent_executor_append)
        result = kalshi_settler.settle_trades(client)

        ids = {t["trade_id"] for t in load_trade_log()}
        assert "A" in ids            # the target trade settled
        assert "CONCURRENT" in ids   # the trade appended mid-fetch survived
        assert result["settled"] == 1

        settled = next(t for t in load_trade_log() if t["trade_id"] == "A")
        assert settled["closed_at"] is not None
