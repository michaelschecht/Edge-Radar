"""Tests for the venue-neutral MarketClient seam (PM2 plumbing)."""

import inspect

import pytest

import market_client as mc
from kalshi_client import KalshiClient

PROTOCOL_METHODS = (
    "get_balance_dollars",
    "get_positions",
    "create_order",
    "get_orders",
    "cancel_order",
    "get_fills",
    "get_settlements",
)


class TestKalshiClientConformance:
    """KalshiClient is the reference implementation — it must satisfy the
    Protocol at class level (no instantiation: __init__ needs credentials)."""

    @pytest.mark.parametrize("name", PROTOCOL_METHODS)
    def test_method_exists_and_callable(self, name):
        assert callable(getattr(KalshiClient, name, None)), (
            f"KalshiClient.{name} missing — MarketClient contract broken")

    @pytest.mark.parametrize("name", PROTOCOL_METHODS)
    def test_signature_covers_protocol_params(self, name):
        # Every parameter the Protocol declares must be accepted by the
        # implementation (drift here would break venue-agnostic callers).
        proto_params = set(inspect.signature(
            getattr(mc.MarketClient, name)).parameters) - {"self"}
        impl_params = set(inspect.signature(
            getattr(KalshiClient, name)).parameters) - {"self"}
        missing = proto_params - impl_params
        assert not missing, f"KalshiClient.{name} missing params: {missing}"

    def test_runtime_checkable_on_conforming_instance(self):
        class Dummy:
            def get_balance_dollars(self): return {}
            def get_positions(self, **kw): return {}
            def create_order(self, ticker, side, action, **kw): return {}
            def get_orders(self, **kw): return {}
            def cancel_order(self, order_id): return {}
            def get_fills(self, **kw): return {}
            def get_settlements(self, **kw): return {}

        assert isinstance(Dummy(), mc.MarketClient)

    def test_runtime_checkable_rejects_partial(self):
        class NotAClient:
            def get_balance_dollars(self): return {}

        assert not isinstance(NotAClient(), mc.MarketClient)


class TestGetMarketClient:
    def test_kalshi_builds_kalshi_client(self, monkeypatch):
        built = []

        class DummyKalshi:
            def __init__(self):
                built.append(True)

        monkeypatch.setattr("kalshi_client.KalshiClient", DummyKalshi)
        client = mc.get_market_client("kalshi")
        assert isinstance(client, DummyKalshi) and built

    def test_default_and_none_resolve_to_kalshi(self, monkeypatch):
        class DummyKalshi:
            pass

        monkeypatch.setattr("kalshi_client.KalshiClient", DummyKalshi)
        assert isinstance(mc.get_market_client(), DummyKalshi)
        assert isinstance(mc.get_market_client(None), DummyKalshi)

    def test_case_and_whitespace_tolerant(self, monkeypatch):
        class DummyKalshi:
            pass

        monkeypatch.setattr("kalshi_client.KalshiClient", DummyKalshi)
        assert isinstance(mc.get_market_client(" Kalshi "), DummyKalshi)

    def test_polymarket_refuses_until_pm2(self):
        with pytest.raises(NotImplementedError, match="Phase 2"):
            mc.get_market_client("polymarket")

    def test_unknown_venue_raises_value_error(self):
        with pytest.raises(ValueError, match="Unknown venue"):
            mc.get_market_client("manifold")
