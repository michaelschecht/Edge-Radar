"""
fees.py -- exchange trading-fee model.

Until 2026-08-25 fees were invisible to the whole system: nothing subtracted
one before a bet, and `log_trade` read `taker_fees_dollars` from the Kalshi v2
create-order response, which does not carry that field -- so every trade in the
log recorded `taker_fees: "0"` and `calculate_pnl` computed
`net_pnl = revenue - cost - 0`.

Measured over the 119 settled trades in the log at that date:

    stake            $140.97
    reported P&L     $-28.32   (-20.1% ROI)
    est. taker fees  $  5.14   (  3.6% of stake)   <- never recorded
    fee-adjusted     $-33.46   (-23.7% ROI)

In *edge* space (the units Gate 3 works in) the drag averaged **1.02 cents per
contract**, against a 3.0-4.0 cent minimum-edge floor -- so the fee was silently
consuming a quarter to a third of the edge the gate was screening for, and up to
58% of it at mid-price where the fee peaks.

Kalshi's published taker fee:

    fee = roundup(rate * C * P * (1 - P))        rounded UP to the next cent

The `roundup` is per *order*, not per contract, which is why it hurts this
bankroll disproportionately: at 1-2 contracts the rounding alone added ~13% on
top of the linear term (0.90c -> 1.02c per contract across the settled book).

`KALSHI_FEE_RATE` exists because the exchange has changed this rate before and
will again -- it is a real-world constant that needs a tuning knob, not a
config-for-config's-sake setting. Set it to 0 to disable fee awareness entirely
(restores pre-2026-08-25 behaviour).

Maker orders are free on Kalshi, so this models the taker case only. The
executor posts marketable limit orders at the ask, so taker is the right
default; a resting order that later fills as maker will simply have been
screened slightly conservatively.
"""

from __future__ import annotations

import math

import paths  # noqa: F401 -- path constants -- configures sys.path
from app.config import get_config

# Kalshi general trading fee rate. See the fee schedule at
# https://kalshi.com/docs/kalshi-fee-schedule.pdf
DEFAULT_FEE_RATE = 0.07


def fee_rate() -> float:
    """Current fee rate, from `KALSHI_FEE_RATE` (0 disables fee awareness)."""
    rate = get_config().gates.kalshi_fee_rate
    return rate if rate >= 0 else DEFAULT_FEE_RATE


def taker_fee(contracts: int, price: float, rate: float | None = None) -> float:
    """Total taker fee in dollars for `contracts` at `price` dollars each.

    Rounds up to the next cent, per order, exactly as Kalshi charges it.
    """
    r = fee_rate() if rate is None else rate
    if r <= 0 or contracts <= 0 or not 0.0 < price < 1.0:
        return 0.0
    return math.ceil(r * contracts * price * (1.0 - price) * 100.0) / 100.0


def fee_per_contract(price: float, rate: float | None = None) -> float:
    """Per-contract fee in dollars -- the linear term, without the per-order roundup.

    This is the right quantity to subtract from an *edge*: both are dollars of
    expected value per contract, so `edge - fee_per_contract(price)` is the net
    edge on the bet. The roundup is deliberately excluded here because order size
    is not known at gate time; it makes this a mild under-estimate (~13% low at
    this bankroll's typical 1-7 contract orders), which errs toward letting a
    marginal bet through rather than blocking a good one.
    """
    r = fee_rate() if rate is None else rate
    if r <= 0 or not 0.0 < price < 1.0:
        return 0.0
    return r * price * (1.0 - price)


def _demo() -> None:
    """Self-check: `python scripts/shared/fees.py`."""
    # Peak fee is at 50c and symmetric around it.
    assert fee_per_contract(0.5, 0.07) > fee_per_contract(0.25, 0.07)
    assert abs(fee_per_contract(0.25, 0.07) - fee_per_contract(0.75, 0.07)) < 1e-12
    # Degenerate prices and disabled rate cost nothing.
    for p in (0.0, 1.0, -0.1, 1.5):
        assert taker_fee(10, p, 0.07) == 0.0, p
    assert taker_fee(10, 0.5, 0.0) == 0.0
    assert fee_per_contract(0.5, 0.0) == 0.0

    # The real trade from the review: 7 contracts @ 14c, claimed edge +4.67%.
    #   0.07 * 7 * 0.14 * 0.86 = $0.0590 -> rounds UP to $0.06
    assert taker_fee(7, 0.14, 0.07) == 0.06, taker_fee(7, 0.14, 0.07)
    # ...which is 6.1% of the $0.98 stake, and 0.86c of the 4.67c claimed edge.
    assert abs(fee_per_contract(0.14, 0.07) - 0.008428) < 1e-6

    # Roundup is per order, so it never scales below one cent.
    assert taker_fee(1, 0.5, 0.07) == 0.02  # 0.0175 -> 0.02

    # Fee is a strict cost: it can only ever reduce a net edge.
    for p in (0.05, 0.14, 0.5, 0.9):
        assert fee_per_contract(p, 0.07) >= 0.0

    print("fees.py self-check passed")
    print(f"  fee/contract at 10c/25c/50c/75c: "
          f"{[round(100 * fee_per_contract(p, 0.07), 2) for p in (0.1, 0.25, 0.5, 0.75)]} cents")


if __name__ == "__main__":
    _demo()
