"""Tests for the PM2 write half: market registry + PolymarketClient (US API)."""

import base64
import inspect
import json
from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import market_client as mc
import market_registry
import polymarket_exec_client as pec
from polymarket_exec_client import PolymarketAPIError, PolymarketClient

# A valid base64 Ed25519 secret (64 bytes) so the lazy signer can build.
_SECRET = base64.b64encode(b"\x01" * 64).decode()


def _opp(ticker="PM-mlb-sd-atl-ml", slug="padres-vs-braves-2026-04-01"):
    return SimpleNamespace(
        ticker=ticker, title="Padres vs. Braves",
        details={"condition_id": "0x9bb9", "market_slug": slug},
    )


def _cfg(dry_run=True, key_id="aa6e3c16-uuid", secret=_SECRET,
         pm_dry_run=None):
    """pm_dry_run defaults to mirroring the global flag so pre-PM2c tests
    that pass dry_run=False still exercise the live-order path."""
    return SimpleNamespace(
        polymarket=SimpleNamespace(key_id=key_id, secret_key=secret,
                                   host="https://api.polymarket.us",
                                   dry_run=dry_run if pm_dry_run is None
                                   else pm_dry_run),
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
        assert entry["market_slug"] == "padres-vs-braves-2026-04-01"
        assert entry["condition_id"] == "0x9bb9"
        assert market_registry.lookup("PM-unknown") is None

    def test_falls_back_to_generic_slug_key(self):
        opp = SimpleNamespace(ticker="PM-x", title="",
                              details={"slug": "some-us-slug"})
        market_registry.record_opportunities([opp])
        assert market_registry.lookup("PM-x")["market_slug"] == "some-us-slug"

    def test_skips_opps_without_slug(self):
        bad = SimpleNamespace(ticker="PM-x", title="",
                              details={"condition_id": "0x1", "clob_token_ids": ["1"]})
        market_registry.record_opportunities([bad])
        assert market_registry.lookup("PM-x") is None

    def test_prunes_expired_entries_on_write(self):
        market_registry.record_opportunities([_opp("PM-old")])
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
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(key_id="", secret=""))
        with pytest.raises(FileNotFoundError, match="POLYMARKET_KEY_ID"):
            PolymarketClient()

    def test_construction_is_network_free(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg())
        client = PolymarketClient()
        assert client._priv is None  # lazy — signer not built yet

    def test_dry_run_blocks_order_without_network_or_registry(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=True))
        client = PolymarketClient()
        resp = client.create_order("PM-any", "yes", "buy", 5, yes_price_cents=44)
        assert resp["status"] == "dry_run_blocked"
        assert client._priv is None

    def test_venue_dry_run_blocks_even_when_global_is_live(self, monkeypatch):
        """PM2c two-flag safety: DRY_RUN=false (live Kalshi) must NOT unlock
        Polymarket orders while POLYMARKET_DRY_RUN stays true."""
        monkeypatch.setattr(pec, "get_config",
                            lambda: _cfg(dry_run=False, pm_dry_run=True))
        client = PolymarketClient()
        assert client.dry_run is True
        resp = client.create_order("PM-any", "yes", "buy", 5, yes_price_cents=44)
        assert resp["status"] == "dry_run_blocked"

    def test_live_requires_both_flags_false(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config",
                            lambda: _cfg(dry_run=False, pm_dry_run=False))
        assert PolymarketClient().dry_run is False
        # Global dry-run still blocks even if the venue flag is flipped.
        monkeypatch.setattr(pec, "get_config",
                            lambda: _cfg(dry_run=True, pm_dry_run=False))
        assert PolymarketClient().dry_run is True

    def test_config_missing_venue_flag_defaults_blocked(self, monkeypatch):
        """A config namespace without the dry_run attr (old shape) stays safe."""
        cfg = _cfg(dry_run=False)
        del cfg.polymarket.dry_run
        monkeypatch.setattr(pec, "get_config", lambda: cfg)
        assert PolymarketClient().dry_run is True

    def test_live_order_builds_no_side_body(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        market_registry.record_opportunities([_opp()])
        client = PolymarketClient()
        client._signed_request = Mock(return_value={"orderId": "ord-1"})

        resp = client.create_order("PM-mlb-sd-atl-ml", "no", "buy", 5,
                                   no_price_cents=57)
        method, path = client._signed_request.call_args.args[:2]
        body = client._signed_request.call_args.kwargs["json_body"]
        assert (method, path) == ("POST", "/v1/orders")
        assert body["marketSlug"] == "padres-vs-braves-2026-04-01"
        assert body["outcomeSide"] == "OUTCOME_SIDE_NO"
        assert body["action"] == "ORDER_ACTION_BUY"
        assert body["price"] == {"value": "0.57", "currency": "USD"}  # NO price, no 1-minus
        assert body["quantity"] == 5.0
        assert resp["orderId"] == "ord-1"

    def test_live_order_yes_side_body(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        market_registry.record_opportunities([_opp()])
        client = PolymarketClient()
        client._signed_request = Mock(return_value={})
        client.create_order("PM-mlb-sd-atl-ml", "yes", "buy", 10,
                            yes_price_cents=44)
        body = client._signed_request.call_args.kwargs["json_body"]
        assert body["outcomeSide"] == "OUTCOME_SIDE_YES"
        assert body["price"]["value"] == "0.44"

    def test_registry_miss_refuses_order(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        client = PolymarketClient()
        with pytest.raises(PolymarketAPIError, match="market_slug"):
            client.create_order("PM-never-scanned", "yes", "buy", 5,
                                yes_price_cents=44)

    def test_missing_price_raises(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg(dry_run=False))
        client = PolymarketClient()
        with pytest.raises(ValueError, match="no_price_cents"):
            client.create_order("PM-x", "no", "buy", 5, yes_price_cents=44)

    def test_balance_parses_usd_and_ignores_reservation(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg())
        client = PolymarketClient()
        client._signed_request = Mock(return_value={"balances": [
            {"currency": "USD", "currentBalance": 60.12, "buyingPower": 60.12,
             "balanceReservation": 50}]})
        # Avoid a second network hop for position value.
        client.get_positions = Mock(return_value={"positions": {}})
        bal = client.get_balance_dollars()
        assert bal["balance"] == 60.12
        assert bal["buying_power"] == 60.12
        assert bal["reservation"] == 50.0  # reported, but not subtracted

    def test_positions_normalize_to_market_positions(self, monkeypatch):
        """PM2c: positions gain a Kalshi-shaped market_positions list whose
        tickers use the scanner's PM-{slug} convention, so the pipeline's
        Gate 5 and show_status consume them unchanged."""
        monkeypatch.setattr(pec, "get_config", lambda: _cfg())
        client = PolymarketClient()
        client._signed_request = Mock(return_value={"positions": {
            "tec-mlb-champ-2026-09-27-mil": {
                "netPosition": 12, "cost": {"value": "4.98"},
                "realized": {"value": "0"},
            },
            "closed-out-market": {"netPosition": 0},
        }})
        resp = client.get_positions()
        mps = resp["market_positions"]
        assert len(mps) == 1  # zero net position filtered out
        assert mps[0]["ticker"] == "PM-tec-mlb-champ-2026-09-27-mil"
        assert mps[0]["position_fp"] == "12.0"
        assert mps[0]["market_exposure_dollars"] == "4.98"
        assert "tec-mlb-champ-2026-09-27-mil" in resp["positions"]  # raw kept

    def test_min_share_warning_uses_registry_minimum(self, monkeypatch, caplog):
        monkeypatch.setattr(pec, "get_config",
                            lambda: _cfg(dry_run=False, pm_dry_run=False))
        opp = _opp()
        opp.details["min_order_shares"] = 10
        market_registry.record_opportunities([opp])
        client = PolymarketClient()
        client._signed_request = Mock(return_value={"orderId": "x"})
        with caplog.at_level("WARNING"):
            client.create_order("PM-mlb-sd-atl-ml", "yes", "buy", 7,
                                yes_price_cents=44)
        assert "10-share minimum" in caplog.text

    def test_signed_request_headers_and_message(self, monkeypatch):
        monkeypatch.setattr(pec, "get_config", lambda: _cfg())
        client = PolymarketClient()
        captured = {}

        def fake_request(method, url, headers=None, json=None, timeout=None):
            captured.update(method=method, url=url, headers=headers)
            return SimpleNamespace(raise_for_status=lambda: None,
                                   content=b"{}", json=lambda: {})

        monkeypatch.setattr(pec.requests, "request", fake_request)
        client._signed_request("GET", "/v1/account/balances")
        assert captured["url"] == "https://api.polymarket.us/v1/account/balances"
        assert captured["headers"]["X-PM-Access-Key"] == "aa6e3c16-uuid"
        assert set(("X-PM-Timestamp", "X-PM-Signature")) <= set(captured["headers"])


class TestFactoryPolymarket:
    def test_factory_builds_polymarket_client(self, monkeypatch):
        class Dummy:
            pass

        monkeypatch.setattr("polymarket_exec_client.PolymarketClient", Dummy)
        assert isinstance(mc.get_market_client("polymarket"), Dummy)
