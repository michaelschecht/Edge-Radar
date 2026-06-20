"""Tests for the Kalshi v2 order-body translation (create-order-v2 migration).

Kalshi deprecated the v1 POST /portfolio/orders endpoint (HTTP 410). The v2
endpoint /portfolio/events/orders is single-book / YES-perspective:
  side "bid" = buy YES, side "ask" = sell YES (= buy NO at 1 - price).
These tests pin the translation, especially the NO->ask inversion where a wrong
mapping would place the opposite position with real money.
"""

import pytest

from kalshi_client import KalshiClient, V2_ORDERS_PATH

build = KalshiClient._build_v2_order_body


class TestV2OrderBody:
    def test_buy_yes_is_bid_at_yes_price(self):
        body = build(
            ticker="KXMLBGAME-26JUN20-T", side="yes", action="buy",
            count=10, yes_price_cents=56, no_price_cents=None,
            time_in_force="good_till_canceled",
        )
        assert body["side"] == "bid"
        assert body["price"] == "0.5600"
        assert body["count"] == "10.00"
        assert body["time_in_force"] == "good_till_canceled"
        assert body["self_trade_prevention_type"] == "taker_at_cross"
        assert "action" not in body and "yes_price" not in body

    def test_buy_no_is_ask_at_one_minus_price(self):
        # Buying NO at $0.40 == selling YES at $0.60.
        body = build(
            ticker="KXWCGAME-26JUN25PARAUS-AUS", side="no", action="buy",
            count=3, yes_price_cents=None, no_price_cents=40,
            time_in_force="good_till_canceled",
        )
        assert body["side"] == "ask"
        assert body["price"] == "0.6000"
        assert body["count"] == "3.00"

    def test_sell_yes_is_ask(self):
        body = build(
            ticker="KXT", side="yes", action="sell",
            count=1, yes_price_cents=70, no_price_cents=None,
            time_in_force="good_till_canceled",
        )
        assert body["side"] == "ask"
        assert body["price"] == "0.7000"

    def test_sell_no_is_bid(self):
        body = build(
            ticker="KXT", side="no", action="sell",
            count=1, yes_price_cents=None, no_price_cents=25,
            time_in_force="good_till_canceled",
        )
        assert body["side"] == "bid"
        assert body["price"] == "0.7500"  # 1 - 0.25

    def test_optional_fields_passed_through(self):
        body = build(
            ticker="KXT", side="yes", action="buy",
            count=2, yes_price_cents=10, no_price_cents=None,
            time_in_force="fill_or_kill",
            client_order_id="abc-123", expiration_ts=1750000000,
        )
        assert body["client_order_id"] == "abc-123"
        assert body["expiration_time"] == 1750000000  # renamed from v1 expiration_ts

    def test_missing_price_raises(self):
        with pytest.raises(ValueError):
            build(
                ticker="KXT", side="yes", action="buy", count=1,
                yes_price_cents=None, no_price_cents=None,
                time_in_force="good_till_canceled",
            )

    def test_bad_side_raises(self):
        with pytest.raises(ValueError):
            build(
                ticker="KXT", side="maybe", action="buy", count=1,
                yes_price_cents=50, no_price_cents=None,
                time_in_force="good_till_canceled",
            )

    def test_endpoint_path_is_v2(self):
        assert V2_ORDERS_PATH == "/portfolio/events/orders"
