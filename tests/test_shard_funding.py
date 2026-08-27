"""Shard funding (2026-08-27): sizing is whole-account, spending is per-shard.

`scripts/shared/shard_funding.py` carries a `_demo()` self-check for the pure
decision logic. These cover the part that matters operationally: that
`_place_order_batch` consults it, honours a refusal by skipping the order, and
never lets a refusal take down the rest of the batch.
"""

import pytest

import kalshi_executor as ke
import shard_funding
from kalshi_executor import _place_order_batch, SizedOrder
from opportunity import Opportunity


def _sized(i, cost=5.0, ticker=None):
    opp = Opportunity(
        ticker=ticker or f"KXMLBGAME-26AUG27T{i}-A",
        title=f"Game {i}", category="game", side="yes",
        market_price=0.50, fair_value=0.60, edge=0.10, edge_source="test",
        confidence="high", liquidity_score=8.0, composite_score=8.5, details={},
    )
    return SizedOrder(opportunity=opp, contracts=10, price_cents=50,
                      cost_dollars=cost, bankroll_pct=0.05, risk_approval="APPROVED")


class _Client:
    """Duck-typed Kalshi client: per-shard balances, scripted market shards."""

    def __init__(self, balances, shards, transfer_lands=True):
        self._b = dict(balances)
        self._shards = dict(shards)
        self._lands = transfer_lands
        self.orders: list[str] = []
        self.transfers: list[tuple[float, int, int]] = []

    def get_market(self, ticker):
        return {"market": {"ticker": ticker,
                           "exchange_index": self._shards.get(ticker)}}

    def get_balance(self):
        return {"balance_breakdown": [{"exchange_index": k, "balance": f"{v:.4f}"}
                                      for k, v in self._b.items()]}

    def intra_exchange_transfer(self, amount, source_shard, destination_shard):
        self.transfers.append((amount, source_shard, destination_shard))
        if self._lands:
            self._b[source_shard] -= amount
            self._b[destination_shard] = self._b.get(destination_shard, 0) + amount
        return {"transfer_id": "t"}

    def create_order(self, **kw):
        self.orders.append(kw["ticker"])
        return {"order_id": "ord", "fill_count": "10.00", "remaining_count": "0.00"}


@pytest.fixture(autouse=True)
def _enable(monkeypatch):
    monkeypatch.setattr(ke, "AUTO_SHARD_TRANSFER", True)
    monkeypatch.setattr(ke, "SHARD_FUNDING_SOURCE", 0)
    monkeypatch.setattr(ke, "MAX_AUTO_SHARD_TRANSFER", 25.0)


def test_tops_up_the_shard_then_places(monkeypatch):
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    c = _Client({0: 70.0, 3: 1.0}, {"KXMLBGAME-26AUG27T0-A": 3})
    tl = []
    results = _place_order_batch(c, [_sized(0, cost=5.0)], tl)

    assert c.transfers == [(4.0, 0, 3)], "moves exactly the shortfall"
    assert c.orders == ["KXMLBGAME-26AUG27T0-A"]
    assert len(results) == 1


def test_no_transfer_when_shard_already_covers_it(monkeypatch):
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    c = _Client({0: 70.0, 3: 40.0}, {"KXMLBGAME-26AUG27T0-A": 3})
    _place_order_batch(c, [_sized(0, cost=5.0)], [])
    assert c.transfers == []
    assert c.orders == ["KXMLBGAME-26AUG27T0-A"]


def test_underfunded_order_is_skipped_not_placed(monkeypatch):
    """The whole point: placing anyway just buys a 404 user_not_found."""
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    monkeypatch.setattr(ke, "MAX_AUTO_SHARD_TRANSFER", 1.0)   # cap below shortfall
    c = _Client({0: 70.0, 3: 0.0}, {"KXMLBGAME-26AUG27T0-A": 3})
    tl = []
    results = _place_order_batch(c, [_sized(0, cost=5.0)], tl)

    assert c.orders == [], "must not reach the venue"
    assert c.transfers == []
    assert results == []
    assert tl and tl[0]["status"] == "error"
    assert "shard_underfunded" in tl[0]["error"]


def test_one_underfunded_order_does_not_stop_the_batch(monkeypatch):
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    monkeypatch.setattr(ke, "MAX_AUTO_SHARD_TRANSFER", 1.0)
    c = _Client(
        {0: 70.0, 3: 0.0},
        {"KXMLBGAME-26AUG27T0-A": 3,    # shard 3, broke -> skipped
         "KXNFLGAME-26SEP13T1-A": 0},   # shard 0, funded -> placed
    )
    orders = [_sized(0, cost=5.0),
              _sized(1, cost=5.0, ticker="KXNFLGAME-26SEP13T1-A")]
    results = _place_order_batch(c, orders, [])

    assert c.orders == ["KXNFLGAME-26SEP13T1-A"]
    assert len(results) == 1


def test_unknown_shard_fails_open(monkeypatch):
    """A market lookup that fails must not block trading as it did pre-sharding."""
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())

    class _NoMarket(_Client):
        def get_market(self, ticker):
            raise RuntimeError("lookup down")

    c = _NoMarket({0: 70.0}, {})
    _place_order_batch(c, [_sized(0, cost=5.0)], [])
    assert c.orders == ["KXMLBGAME-26AUG27T0-A"]
    assert c.transfers == []


def test_market_is_looked_up_once_per_ticker(monkeypatch):
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    c = _Client({0: 70.0, 3: 90.0}, {"KXMLBGAME-26AUG27T0-A": 3})
    seen = []
    orig = c.get_market
    c.get_market = lambda t: (seen.append(t), orig(t))[1]

    same = [_sized(0, cost=1.0), _sized(0, cost=1.0), _sized(0, cost=1.0)]
    _place_order_batch(c, same, [])
    assert seen == ["KXMLBGAME-26AUG27T0-A"], "shard lookup must be cached per batch"


def test_transfer_that_does_not_settle_blocks_the_order(monkeypatch):
    """Kalshi's transfer is non-atomic; a 200 is not proof the money arrived."""
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    c = _Client({0: 70.0, 3: 0.0}, {"KXMLBGAME-26AUG27T0-A": 3},
                transfer_lands=False)
    tl = []
    _place_order_batch(c, [_sized(0, cost=5.0)], tl)

    assert c.transfers, "it did attempt the move"
    assert c.orders == [], "but must not place against money that never landed"
    assert "did not settle" in tl[0]["error"]


def test_disabled_flag_skips_rather_than_moving_money(monkeypatch):
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    monkeypatch.setattr(ke, "AUTO_SHARD_TRANSFER", False)
    c = _Client({0: 70.0, 3: 0.0}, {"KXMLBGAME-26AUG27T0-A": 3})
    tl = []
    _place_order_batch(c, [_sized(0, cost=5.0)], tl)
    assert c.transfers == [] and c.orders == []
    assert "AUTO_SHARD_TRANSFER is off" in tl[0]["error"]


def test_dry_run_never_moves_money(monkeypatch):
    monkeypatch.setattr(ke, "vel", _AlwaysEligible())
    ok, note = shard_funding.ensure_shard_funded(
        _Client({0: 70.0, 3: 0.0}, {}), 3, 5.0,
        enabled=True, source_shard=0, max_transfer=25.0, dry_run=True,
    )
    assert ok and "[dry-run]" in note


class _AlwaysEligible:
    """Stand-in for `venue_eligibility` so these tests exercise shard logic only."""

    @staticmethod
    def product_for(category):
        return "sports"

    @staticmethod
    def record_success(*a, **kw):
        return None

    @staticmethod
    def record_rejection(*a, **kw):
        return False

    @staticmethod
    def actionable_reason(raw, limit=160):
        return str(raw)
