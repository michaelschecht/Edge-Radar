"""F2 (2026-08-25): the limit price posted to the exchange.

`size_order` computed `price_cents = int(opp.market_price * 100)`, which
truncates: `0.29 * 100 == 28.999999999999996`, so a 29c ask posted a 28c limit —
one cent below the book, which never fills. Silent, because the order rests
rather than erroring.

`price_cents` is the actual limit price on both venues: Kalshi via
`_build_v2_order_body` (`"price": f"{yes_price_cents_eff / 100:.4f}"`, and NO
orders through `100 - no_price_cents`), Polymarket via
`"price": {"value": f"{price_cents / 100:.2f}"}`.
"""

import pytest
from opportunity import Opportunity

from kalshi_executor import size_order


def _opp(price: float, side: str = "yes", edge: float = 0.50) -> Opportunity:
    return Opportunity(
        ticker="KXMLBGAME-99APR171900NYYKAC-NYY", title="Test", category="game",
        side=side, market_price=price, fair_value=min(0.99, price + edge),
        edge=edge, edge_source="test", confidence="high",
        liquidity_score=8.0, composite_score=9.0, details={},
    )


@pytest.fixture(autouse=True)
def _open_the_gates(monkeypatch):
    """Disable the reject gates that are irrelevant here.

    Gate 3.5 (`MIN_MARKET_PRICE`, live .env = 0.10) rejects cheap prices, and a
    rejected SizedOrder carries `price_cents=0` -- which would make the sub-10c
    parametrisations test the price floor instead of the cent conversion.
    """
    import kalshi_executor as ke
    monkeypatch.setattr(ke, "MIN_MARKET_PRICE", 0.0)
    monkeypatch.setattr(ke, "MIN_COMPOSITE_SCORE", 0.0)
    monkeypatch.setattr(ke, "NO_SIDE_FAVORITE_THRESHOLD", 0.0)


def _cents(price: float, side: str = "yes") -> int:
    sized = size_order(_opp(price, side), bankroll=10000.0,
                       open_positions=0, daily_pnl=0.0)
    assert sized.risk_approval.startswith("APPROVED"), sized.risk_approval
    return sized.price_cents


class TestEveryCentRoundTrips:
    @pytest.mark.parametrize("cent", range(1, 100))
    def test_exact_cent_price_posts_that_cent(self, cent):
        # Kalshi quotes exact cents. The limit must equal the ask -- posting one
        # cent under is an unfillable order, posting one over overpays.
        assert _cents(round(cent / 100, 4)) == cent

    @pytest.mark.parametrize("cent", [29, 57, 58])
    def test_the_three_prices_int_truncation_broke(self, cent):
        # Regression pin: these are the exact values `int(price * 100)` got wrong.
        assert int(round(cent / 100, 4) * 100) == cent - 1   # the old bug
        assert _cents(round(cent / 100, 4)) == cent          # the fix

    @pytest.mark.parametrize("cent", [29, 57, 58])
    def test_no_side_inherits_the_fix(self, cent):
        # NO orders reach the book as `100 - no_price_cents`, so a truncated NO
        # price posts a YES ask one cent too high -- equally unfillable.
        assert _cents(round(cent / 100, 4), side="no") == cent


class TestSubCentAsksAreNotUnderPosted:
    @pytest.mark.parametrize("price,expected", [
        (0.235, 24),    # Polymarket Gamma bestAsk is not cent-aligned
        (0.607, 61),
        (0.501, 51),    # plain round() would post 50c -- below the ask
        (0.0125, 2),    # plain round() would post 1c -- below the ask
    ])
    def test_marketable_buy_never_posts_below_the_ask(self, price, expected):
        assert _cents(price) == expected
        assert _cents(price) / 100 >= price


class TestClamps:
    def test_price_at_or_above_a_dollar_clamps_to_99(self):
        assert _cents(0.9985) == 99

    def test_sub_penny_price_clamps_to_1(self):
        assert _cents(0.001) == 1
