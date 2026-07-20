"""Tests for the PM2 write half: market registry + PolymarketClient."""

import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import market_client as mc
import market_registry
import polymarket_exec_client as pec
from polymarket_exec_client import PolymarketAPIError, PolymarketClient


def _opp(ticker="PM-mlb-sd-atl-ml", tokens=("111", "222")):
    return SimpleNamespace(
        ticker=ticker, title="Padres vs. Braves",
        details={"condition_id": "0x9bb9", "clob_token_ids": list(tokens)},
    )


def _cfg(dry_run=True, key="0x" + "11" * 32, funder="0xFUNDER"):
    return SimpleNamespace(
        polymarket=SimpleNamespace(private_key=key, funder_address=funder,
                                   signature_type=1,
                                   host="https://clob.polymarket.com"),
        system=SimpleNamespace(dry_run=dry_run),
    )


# ── market_registry ──────────────────────────────────────────────────────────

class TestMarketRegistry:
    @pytest.fixture(autouse=True)
    def _tmp_registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr(market_registry, "REGISTRY_PATH",
                            tmp_path / "market_registry.json")

    def test_record_and_lookup_roundtrip(self):
        market_registry.record_opportunities([_opp()])
        entry = market_registry.lookup("PM-mlb-sd-atl-ml")
        assert entry["clob_token_ids"] == ["111", "222"]
        assert entry["condition_id"] == "0x9bb9"
        assert market_registry.lookup("PM-unknown") is None

    def test_skips_opps_without_tokens(self):
        bad = SimpleNamespace(ticker="PM-x", title="", details={})
        market_registry.record_opportunities([bad])
        assert market_registry.lookup("PM-x") is None

    def test_prunes_expired_entries_on_write(self):
        market_registry.record_opportunities([_opp("PM-old")])
        # Backdate the stored entry past MAX_AGE_DAYS, then trigger a write.
        raw = json.loads(market_registry.REGISTRY_PATH.read_text())
        raw["PM-old"]["recorded_at"] = "2000-01-01T00:00:00+00:00"
        market_registry.REGISTRY_PATH.write_text(json.dumps(raw))
        market_registry.record_opportunities([_opp("PM-new")])
        assert market_registry.lookup("PM-old") is None
        assert market_registry.lookup("PM-new") is not None


# ── PolymarketClient ─────────────────────────────────────────────────────────

class TestPolymarketClientConformance:
    @pytest.mark.parametrize("name", (
        "get_balance_dollars", "get_positions", "create_order", "get_orders",
        "cancel_order", "get_fills", "get_settlements"))
    def test_signature_covers_protocol_params(self, name):
        proto_params = set(inspect.signature(
            getattr(mc.MarketClient, name)).parameters) - {"self"}
        impl_params = set(inspect.signature(
            getattr(PolymarketClient, name)).parameters) - {"self"}
        missing = proto_params - impl_params
        assert not missing, f"PolymarketClient.{name} missing params: {missing}"


class TestPolymarketClient:
    @pytest.fixture(autouse=True)
    def _tmp_registry(self, tmp_path, monkeypatch):
        monkeypatch.setattr(market_registry, "REGISTRY_PATH",
                            tmp_path / "market_registry.json")

    def test_missing_creds_raise_with_guidance(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(key="", funder=""))
        with pytest.raises(FileNotFoundError, match="POLYMARKET_PRIVATE_KEY"):
            PolymarketClient()

    def test_construction_is_network_free(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg())
        client = PolymarketClient()
        assert client._clob_instance is None  # lazy — nothing built yet

    def test_dry_run_blocks_order_without_clob_or_registry(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=True))
        client = PolymarketClient()
        resp = client.create_order("PM-any", "yes", "buy", 5, yes_price_cents=44)
        assert resp["status"] == "dry_run_blocked"
        assert client._clob_instance is None

    def test_live_order_resolves_no_side_to_token_1(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        market_registry.record_opportunities([_opp()])
        client = PolymarketClient()
        clob = Mock()
        clob.create_order.return_value = "SIGNED"
        clob.post_order.return_value = {"orderID": "ord-1", "success": True}
        client._clob_instance = clob

        resp = client.create_order("PM-mlb-sd-atl-ml", "no", "buy", 5,
                                   no_price_cents=57)
        args = clob.create_order.call_args.args[0]
        assert args.token_id == "222"       # NO side = second token
        assert args.price == 0.57           # NO price used directly (no 1-minus)
        assert args.size == 5.0
        clob.post_order.assert_called_once()
        assert resp["orderID"] == "ord-1"

    def test_live_order_yes_side_uses_token_0(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        market_registry.record_opportunities([_opp()])
        client = PolymarketClient()
        clob = Mock()
        clob.post_order.return_value = {}
        client._clob_instance = clob
        client.create_order("PM-mlb-sd-atl-ml", "yes", "buy", 10,
                            yes_price_cents=44)
        args = clob.create_order.call_args.args[0]
        assert args.token_id == "111" and args.price == 0.44

    def test_registry_miss_refuses_order(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        client = PolymarketClient()
        with pytest.raises(PolymarketAPIError, match="registry"):
            client.create_order("PM-never-scanned", "yes", "buy", 5,
                                yes_price_cents=44)

    def test_missing_price_raises(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        client = PolymarketClient()
        with pytest.raises(ValueError, match="no_price_cents"):
            client.create_order("PM-x", "no", "buy", 5, yes_price_cents=44)


class TestFactoryPolymarket:
    def test_factory_builds_polymarket_client(self, monkeypatch):
        class Dummy:
            pass

        monkeypatch.setattr("polymarket_exec_client.PolymarketClient", Dummy)
        assert isinstance(mc.get_market_client("polymarket"), Dummy)
