"""S21: cash committed to resting orders must reach Gate 2b.

A resting order is invisible to every input Gate 2b had. It is not a position,
so `exposure_from_positions` returns 0 for it, and its cash has already left
`balance` without arriving in `portfolio_value`. That shrinks equity AND leaves
exposure unchanged -- understating the ratio in both terms at once, so the gate
reads looser than it was configured to be.

Observed 2026-08-31: `KXMLBTOTAL-26AUG311940MILCHC-14` requested 3 contracts for
$2.43 and logged `contracts: 0, cost_dollars: 0.00`, while shard 3 fell from
$15.00 to $12.57 -- exactly the $2.43.
"""

import pytest

from kalshi_executor import resting_exposure


class _Client:
    """Minimal stand-in for the venue's resting-order listing."""

    def __init__(self, orders, raises=False):
        self._orders = orders
        self._raises = raises

    def get_orders(self, status=None, limit=None):
        if self._raises:
            raise RuntimeError("venue unavailable")
        assert status == "resting"      # never count filled/cancelled orders
        return {"orders": self._orders}


def _order(order_id="o1", ticker="KXMLBTOTAL-26AUG311940MILCHC-14", remaining=3):
    return {"order_id": order_id, "ticker": ticker,
            "remaining_count": str(remaining)}


def _logged(order_id="o1", price_cents=81):
    return {"order_id": order_id, "price_cents": price_cents}


class TestPricingComesFromTheLog:
    def test_the_real_2026_08_31_order(self):
        """The order that exposed this: 3 contracts, 81c NO, $2.43."""
        total, by_seg = resting_exposure(_Client([_order()]), [_logged()])
        assert total == pytest.approx(2.43)
        assert by_seg == {"mlb": pytest.approx(2.43)}

    def test_no_side_is_not_inverted(self):
        """The whole reason price comes from the log, not the venue.

        v2 expresses orders YES-side, so an 81c NO rests as an `ask` at 0.19.
        Pricing off the venue payload without inverting would count $0.57 where
        the truth is $2.43 -- a 4x under-count in the gate this is tightening.
        The log stores `price_cents` bet-side, so no inversion is possible.
        """
        venue_order = _order(remaining=3)
        venue_order["side"] = "ask"          # v2 YES-perspective for a NO buy
        venue_order["price"] = "0.1900"      # 1 - 0.81, the trap
        total, _ = resting_exposure(_Client([venue_order]), [_logged(price_cents=81)])
        assert total == pytest.approx(2.43)
        assert total != pytest.approx(0.57)

    def test_segments_split_like_positions_do(self):
        orders = [_order("o1", "KXMLBTOTAL-26AUG311940MILCHC-14", 3),
                  _order("o2", "KXNFLSPREAD-99SEP13BALIND-IND5", 2)]
        rows = [_logged("o1", 81), _logged("o2", 50)]
        total, by_seg = resting_exposure(_Client(orders), rows)
        assert total == pytest.approx(2.43 + 1.00)
        assert by_seg["mlb"] == pytest.approx(2.43)
        assert by_seg["nfl"] == pytest.approx(1.00)


class TestUnpriceableOrdersErrTight:
    def test_order_missing_from_the_log_is_counted_at_worst_case(self, caplog):
        """A hand-placed iOS order has no log row. Counting it at $0 would
        reproduce the exact under-count this function removes, so it is counted
        at $1.00/contract -- over-stating exposure only ever tightens the gate.
        """
        with caplog.at_level("WARNING"):
            total, by_seg = resting_exposure(_Client([_order(remaining=3)]), [])
        assert total == pytest.approx(3.00)
        assert "not priceable" in caplog.text

    @pytest.mark.parametrize("bad", [None, "", "abc", 0, -5, 150])
    def test_garbage_price_falls_back_rather_than_computing_nonsense(self, bad):
        total, _ = resting_exposure(_Client([_order(remaining=2)]),
                                    [_logged(price_cents=bad)])
        assert total == pytest.approx(2.00)


class TestItNeverBlocksABatch:
    def test_venue_error_returns_zero_and_warns(self, caplog):
        """Exposure data is a sizing input, not a legality check (contrast S3):
        failing open is right, but it must say so."""
        with caplog.at_level("WARNING"):
            total, by_seg = resting_exposure(_Client([], raises=True))
        assert (total, by_seg) == (0.0, {})
        assert "under-count" in caplog.text

    def test_no_resting_orders_is_free(self):
        assert resting_exposure(_Client([]), []) == (0.0, {})

    def test_fully_filled_order_contributes_nothing(self):
        """remaining_count 0 means the cash became a position; counting it here
        as well would double-count it against `exposure_from_positions`."""
        total, _ = resting_exposure(_Client([_order(remaining=0)]), [_logged()])
        assert total == 0.0

    def test_fixed_point_remaining_count_is_handled(self):
        """List/get endpoints return the `_fp` variants (see `_order_field`)."""
        o = {"order_id": "o1", "ticker": "KXMLBTOTAL-26AUG311940MILCHC-14",
             "remaining_count_fp": "3.00"}
        total, _ = resting_exposure(_Client([o]), [_logged()])
        assert total == pytest.approx(2.43)
