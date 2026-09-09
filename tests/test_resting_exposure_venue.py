"""S27: `resting_exposure` must fail open, and must not be asked on Polymarket.

Polymarket US answers `GET /v1/orders` with 501 (gRPC code 12 UNIMPLEMENTED),
deterministically. Ungated, S21's exposure call logged a WARNING on every PM run
from 2026-08-31 -- the S25 failure mode, where a line that fires unconditionally
stops being read and takes the real signal with it.

The guard itself (`venue == "kalshi"` in `execute_pipeline`) is one line matching
the janitor's identical guard two lines above it, which is also untested: reaching
it needs a full authenticated venue round-trip, and a harness built only to prove
an `if` is scaffolding. What IS worth pinning is the contract it leans on -- that
a venue error can never block a batch -- because that is the behaviour that makes
failing open safe in the first place.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "kalshi"))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts" / "shared"))
import kalshi_executor


class _OrdersUnimplemented:
    """Stands in for the Polymarket US client: listing orders is a hard error."""

    def __init__(self):
        self.calls = 0

    def get_orders(self, *a, **kw):
        self.calls += 1
        raise RuntimeError('GET /v1/orders -> 501: {"code":12,"message":'
                           '"The server was unable to process your request."}')


def test_resting_exposure_fails_open_on_a_venue_error():
    """S21's contract: exposure is a sizing input, so a listing failure must
    return zero rather than raise. Contrast S3, which fails closed."""
    client = _OrdersUnimplemented()
    assert kalshi_executor.resting_exposure(client, []) == (0.0, {})
    assert client.calls == 1


def test_resting_exposure_fails_open_on_a_client_missing_the_method():
    """A venue whose client has no `get_orders` at all must behave the same --
    the bare `except Exception` is load-bearing, not lazy."""
    assert kalshi_executor.resting_exposure(object(), []) == (0.0, {})
