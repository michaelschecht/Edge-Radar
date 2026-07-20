"""Tests for batch-execution resilience to network failures (repo review #7).

Two layers:
1. `KalshiClient._request` translates a raw `requests` transport error (no HTTP
   response) into a typed `KalshiConnectionError` instead of a bare traceback.
2. `_place_order_batch` no longer aborts the whole batch on one order's failure:
   API errors and transport errors are recorded per-order and the loop
   continues, with a circuit-breaker after consecutive transport failures.
"""

import pytest
import requests

import kalshi_client
from kalshi_client import KalshiClient, KalshiAPIError, KalshiConnectionError
from kalshi_executor import _place_order_batch, SizedOrder, MAX_CONSECUTIVE_CONN_ERRORS
from opportunity import Opportunity


# ── Layer 1: client translates transport errors ───────────────────────────────

def _bare_client(monkeypatch):
    """A KalshiClient without RSA/auth setup — enough to exercise `_request`."""
    c = KalshiClient.__new__(KalshiClient)
    c.base_url = "https://example.test"
    c.api_key = "k"
    monkeypatch.setattr(c, "_auth_headers", lambda method, path: {})
    return c


class TestRequestTransportTranslation:
    def test_connection_error_becomes_kalshi_connection_error(self, monkeypatch):
        c = _bare_client(monkeypatch)
        monkeypatch.setattr(
            kalshi_client.requests, "request",
            lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.ConnectionError("refused")),
        )
        with pytest.raises(KalshiConnectionError) as ei:
            c._request("POST", "/portfolio/events/orders", body={"x": 1})
        assert ei.value.status_code == 0
        assert "ConnectionError" in ei.value.message

    def test_timeout_becomes_kalshi_connection_error(self, monkeypatch):
        c = _bare_client(monkeypatch)
        monkeypatch.setattr(
            kalshi_client.requests, "request",
            lambda *a, **k: (_ for _ in ()).throw(requests.exceptions.Timeout("t")),
        )
        with pytest.raises(KalshiConnectionError):
            c._request("GET", "/markets")

    def test_connection_error_is_catchable_as_api_error(self):
        # subclass relationship => existing `except KalshiAPIError` handlers catch it
        assert issubclass(KalshiConnectionError, KalshiAPIError)


# ── Layer 2: batch resilience ─────────────────────────────────────────────────

def _sized(i):
    opp = Opportunity(
        ticker=f"KXNBAGAME-26APR04T{i}-A",
        title=f"Game {i}",
        category="game",
        side="yes",
        market_price=0.50,
        fair_value=0.60,
        edge=0.10,
        edge_source="test",
        confidence="high",
        liquidity_score=8.0,
        composite_score=8.5,
        details={},
    )
    return SizedOrder(
        opportunity=opp, contracts=10, price_cents=50,
        cost_dollars=5.0, bankroll_pct=0.05, risk_approval="APPROVED",
    )


def _sized_list(n):
    return [_sized(i) for i in range(n)]


def _ok(fill=10, remaining=0):
    return ("ok", {"order_id": "ord", "fill_count": f"{fill}.00", "remaining_count": f"{remaining}.00"})


class _ScriptedClient:
    """create_order plays back a scripted list of ("ok", resp) / ("raise", exc)."""

    def __init__(self, behaviors):
        self._behaviors = list(behaviors)
        self.calls = 0

    def create_order(self, **kwargs):
        self.calls += 1
        kind, payload = self._behaviors.pop(0)
        if kind == "raise":
            raise payload
        return payload


class TestBatchResilience:
    def test_api_error_records_and_continues(self):
        behaviors = [_ok(), ("raise", KalshiAPIError(400, "bad request")), _ok()]
        client = _ScriptedClient(behaviors)
        tl = []
        results = _place_order_batch(client, _sized_list(3), tl)
        assert client.calls == 3            # every order attempted — no mid-batch abort
        assert len(results) == 2            # two placed
        errs = [t for t in tl if t.get("status") == "error"]
        assert len(errs) == 1

    def test_connection_error_records_flagged_and_continues(self):
        behaviors = [("raise", KalshiConnectionError("Timeout: t")), _ok()]
        client = _ScriptedClient(behaviors)
        tl = []
        results = _place_order_batch(client, _sized_list(2), tl)
        assert client.calls == 2
        assert len(results) == 1
        errs = [t for t in tl if t.get("status") == "error"]
        assert len(errs) == 1
        assert "reconcile" in errs[0]["error"].lower()  # flagged as placement-unknown

    def test_stops_after_consecutive_connection_failures(self):
        behaviors = [("raise", KalshiConnectionError("down"))] * 5
        client = _ScriptedClient(behaviors)
        results = _place_order_batch(client, _sized_list(5), [])
        assert results == []
        # broke after the Nth consecutive failure — later orders never attempted
        assert client.calls == MAX_CONSECUTIVE_CONN_ERRORS

    def test_success_resets_consecutive_counter(self):
        # conn, ok, conn, ok, conn — never 3 in a row, so the batch runs to the end
        behaviors = [
            ("raise", KalshiConnectionError("a")), _ok(),
            ("raise", KalshiConnectionError("b")), _ok(),
            ("raise", KalshiConnectionError("c")),
        ]
        client = _ScriptedClient(behaviors)
        results = _place_order_batch(client, _sized_list(5), [])
        assert client.calls == 5
        assert len(results) == 2

    def test_api_error_resets_consecutive_counter(self):
        # A real HTTP status between transport blips means the network is fine.
        behaviors = [
            ("raise", KalshiConnectionError("a")),
            ("raise", KalshiConnectionError("b")),
            ("raise", KalshiAPIError(500, "server")),   # resets the counter
            ("raise", KalshiConnectionError("c")),
            ("raise", KalshiConnectionError("d")),
        ]
        client = _ScriptedClient(behaviors)
        _place_order_batch(client, _sized_list(5), [])
        assert client.calls == 5   # never 3 consecutive transport failures
