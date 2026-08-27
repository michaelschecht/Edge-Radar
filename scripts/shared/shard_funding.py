"""Just-in-time cash movement between Kalshi exchange shards.

Kalshi sharded the exchange on **2026-08-24**: Crypto moved to shard 2, Tennis &
Baseball to shard 3, everything else stayed on shard 0. **Cash does not follow the
markets.** An order against a market on a shard where the account holds no funds
fails `404 user_not_found` -- the market resolves, then the per-shard user lookup
does not (see CHANGELOG 2026-08-27).

Sizing is deliberately whole-account: `bankroll` is `get_balance()["balance"]`, the
sum across every shard (operator's call, 2026-08-27). So an order can be correctly
sized against the full balance and still be unspendable where it lands. This module
closes that gap by moving exactly the shortfall from the funding shard immediately
before the order is placed.

**Design constraints, all learned the hard way:**

* **Exactly the shortfall, never a round-up.** Cash parked on a sports shard cannot
  back an NFL order. Over-moving quietly reallocates the bankroll.
* **Capped.** `MAX_AUTO_SHARD_TRANSFER` bounds a single move. A shortfall computed
  wrongly should bounce off the cap, not drain shard 0.
* **Verified, not assumed.** Kalshi: "Cross-exchange-index subaccount transfers run
  in up to three non-atomic steps. If a later step fails, completed steps are not
  undone." So the destination balance is re-read afterwards, and the order is
  skipped if the money did not arrive.
* **Never in DRY_RUN.** `intra_exchange_transfer()` blocks it too; this is the
  belt to that suspenders, because the whole point is unattended operation.
* **One attempt per order.** No retry loop around a money movement.
"""

from __future__ import annotations

import logging

log = logging.getLogger("shard_funding")

__all__ = ["shard_balances", "ensure_shard_funded"]


def shard_balances(client) -> dict[int, float]:
    """Map shard index -> available dollars, from `balance_breakdown`.

    The top-level `balance` is the SUM across shards and is what sizing uses;
    this is the per-shard view that determines what an order can actually spend.
    """
    raw = client.get_balance() or {}
    out: dict[int, float] = {}
    for row in raw.get("balance_breakdown") or []:
        idx = row.get("exchange_index")
        if idx is None:
            continue
        try:
            out[int(idx)] = float(row.get("balance") or 0.0)
        except (TypeError, ValueError):
            continue
    return out


def ensure_shard_funded(client, shard: int | None, cost: float, *,
                        enabled: bool, source_shard: int, max_transfer: float,
                        dry_run: bool) -> tuple[bool, str | None]:
    """Make `cost` spendable on `shard`, moving cash from `source_shard` if needed.

    Returns ``(ok, note)``. ``ok`` False means do not place this order. ``note`` is
    a human line for the console/log when something happened worth saying; None
    when nothing needed doing.

    Fails **open** on a shard we cannot identify (``shard is None``): pre-sharding
    behaviour, and the venue's own error is the backstop. Fails **closed** on a
    transfer that did not land -- an order placed against money that never arrived
    is the failure this exists to prevent.
    """
    if shard is None or shard == source_shard:
        return True, None

    balances = shard_balances(client)
    if not balances:
        # No breakdown (older API shape, or a stubbed client) -- nothing to
        # reason about. Let the venue arbitrate, as it did before sharding.
        return True, None

    available = balances.get(shard, 0.0)
    if available >= cost:
        return True, None

    shortfall = round(cost - available, 4)

    if not enabled:
        return False, (f"shard {shard} holds ${available:,.2f}, needs ${cost:,.2f} "
                       f"— short ${shortfall:,.2f}. AUTO_SHARD_TRANSFER is off.")

    if shortfall > max_transfer:
        return False, (f"shard {shard} short ${shortfall:,.2f}, over the "
                       f"${max_transfer:,.2f} single-transfer cap — not moved.")

    source_available = balances.get(source_shard, 0.0)
    if source_available < shortfall:
        return False, (f"shard {shard} short ${shortfall:,.2f} but shard "
                       f"{source_shard} only holds ${source_available:,.2f}.")

    if dry_run:
        return True, (f"[dry-run] would move ${shortfall:,.2f} "
                      f"shard {source_shard} -> {shard}")

    log.info("Auto-funding shard %s: $%.4f from shard %s (need $%.2f, have $%.2f)",
             shard, shortfall, source_shard, cost, available)
    try:
        client.intra_exchange_transfer(shortfall, source_shard=source_shard,
                                       destination_shard=shard)
    except Exception as e:                                  # noqa: BLE001
        log.error("Auto shard transfer failed (%s -> %s, $%.4f): %s",
                  source_shard, shard, shortfall, e)
        return False, f"shard transfer failed: {e}"

    # Non-atomic: confirm it actually landed rather than trusting the 200.
    settled = shard_balances(client).get(shard, 0.0)
    if settled < cost:
        log.error("Transfer to shard %s reported success but balance is $%.4f, "
                  "need $%.2f — order skipped, funds may be mid-flight.",
                  shard, settled, cost)
        return False, (f"transfer to shard {shard} did not settle "
                       f"(${settled:,.2f} < ${cost:,.2f}) — order skipped")

    return True, (f"moved ${shortfall:,.2f} shard {source_shard} -> {shard} "
                  f"(now ${settled:,.2f})")


def _demo() -> None:
    """Self-check — no network, no money."""

    class FakeClient:
        def __init__(self, balances, transfer_lands=True, raises=None):
            self._b = dict(balances)
            self._lands = transfer_lands
            self._raises = raises
            self.transfers: list[tuple[float, int, int]] = []

        def get_balance(self):
            return {"balance_breakdown": [{"exchange_index": k, "balance": f"{v:.4f}"}
                                          for k, v in self._b.items()]}

        def intra_exchange_transfer(self, amount, source_shard, destination_shard):
            if self._raises:
                raise self._raises
            self.transfers.append((amount, source_shard, destination_shard))
            if self._lands:
                self._b[source_shard] -= amount
                self._b[destination_shard] = self._b.get(destination_shard, 0) + amount
            return {"transfer_id": "fake"}

    kw = dict(enabled=True, source_shard=0, max_transfer=25.0, dry_run=False)

    # already funded -> no transfer
    c = FakeClient({0: 70.0, 3: 15.0})
    assert ensure_shard_funded(c, 3, 10.0, **kw) == (True, None)
    assert c.transfers == []

    # funding shard itself is never topped up from itself
    assert ensure_shard_funded(c, 0, 10.0, **kw) == (True, None)

    # unknown shard fails OPEN (pre-sharding behaviour)
    assert ensure_shard_funded(c, None, 10.0, **kw) == (True, None)

    # shortfall moved exactly, not rounded up
    c = FakeClient({0: 70.0, 3: 2.0})
    ok, note = ensure_shard_funded(c, 3, 10.0, **kw)
    assert ok and c.transfers == [(8.0, 0, 3)], c.transfers
    assert "moved $8.00" in note

    # over the cap -> refused, nothing moved
    c = FakeClient({0: 70.0, 3: 0.0})
    ok, note = ensure_shard_funded(c, 3, 40.0, **{**kw, "max_transfer": 25.0})
    assert not ok and "cap" in note and c.transfers == []

    # source too poor -> refused
    c = FakeClient({0: 3.0, 3: 0.0})
    ok, note = ensure_shard_funded(c, 3, 10.0, **kw)
    assert not ok and "only holds" in note and c.transfers == []

    # disabled -> refused, and says so
    c = FakeClient({0: 70.0, 3: 0.0})
    ok, note = ensure_shard_funded(c, 3, 10.0, **{**kw, "enabled": False})
    assert not ok and "AUTO_SHARD_TRANSFER is off" in note and c.transfers == []

    # dry run -> approved, nothing moved
    c = FakeClient({0: 70.0, 3: 0.0})
    ok, note = ensure_shard_funded(c, 3, 10.0, **{**kw, "dry_run": True})
    assert ok and "[dry-run]" in note and c.transfers == []

    # transfer raises -> refused
    c = FakeClient({0: 70.0, 3: 0.0}, raises=RuntimeError("boom"))
    ok, note = ensure_shard_funded(c, 3, 10.0, **kw)
    assert not ok and "failed" in note

    # non-atomic partial: 200 OK but money never landed -> refused
    c = FakeClient({0: 70.0, 3: 0.0}, transfer_lands=False)
    ok, note = ensure_shard_funded(c, 3, 10.0, **kw)
    assert not ok and "did not settle" in note

    print("shard_funding self-check OK")


if __name__ == "__main__":
    _demo()
