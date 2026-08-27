"""S3 (2026-08-26): venue/product eligibility — classify, remember, fail closed.

**The bug this exists for.** Between 2026-08-20 and 2026-08-25 Kalshi rejected
**16 orders across 6 scheduled runs** with:

    Nevada_residents_are_not_currently_allowed_to_open_positions_in_Sports,
    _Elections_and_Entertainment._Check_your_email_for_more_details.

The account is not in Nevada. That text is what an API key receives when it has
not completed Kalshi's periodic **geolocation check** — the fix was a two-minute
click-through, and it took six days to find. Three things went wrong, and this
module addresses all three:

1. **Nothing stopped the batch.** `_place_order_batch` catches `KalshiAPIError`,
   records it, and keeps placing — correct for a 429 or a stale price, wrong for
   a jurisdiction block, which is deterministic. Every order after the first in
   a run was knowably doomed: 08-20 fired 3 within one second, 08-23 fired 4.
2. **Nothing remembered.** Each run started fresh and re-discovered the block.
3. **Nothing said what to do.** The instruction sits at the *end* of the
   message, and all three reporting surfaces truncate the end.

**Fail closed, deliberately.** `unknown` blocks live orders, unlike the risk
gates (3.6, 3.7, 2b) which fail *open* on missing data. The asymmetry is the
point: an unmeasurable spread is a sizing question and the worst case is a bad
bet, while an unverified jurisdiction is a legality question and the worst case
is an order the venue is legally barred from filling.

**Nothing here clears a block automatically.** Auto-retry is precisely the
behaviour that produced six days of rejections. `record_success()` promotes only
on a *real fill*, and `doctor.py --verify-eligibility` is an explicit,
operator-invoked probe.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timedelta, timezone

import paths

ELIGIBILITY_PATH = paths.VENUE_ELIGIBILITY_PATH

# How long an `ok` verdict stands before it decays back to `unknown`. Kalshi
# says it "will send further instructions as necessary to maintain access", so
# eligibility is a lease, not a fact. 30 days is long enough not to nag and
# short enough that a silently-expired check surfaces before a full season of
# scheduled runs walks into it.
ELIGIBILITY_TTL_DAYS = 30

# Patterns that mean "this account/key may not trade this product here" —
# deterministic, and re-sending the same order will fail identically.
#
# Matched against the whole raw error body (code AND message), lowercased, with
# the underscores Kalshi uses in `code` normalised to spaces so one pattern
# covers both fields. Kept deliberately narrow: a false positive here disables a
# venue, so a merely *unusual* error must fall through to the transient path.
_STRUCTURAL_PATTERNS = (
    r"residents are not currently allowed",      # the observed geo/geolocation block
    r"not (?:currently )?allowed to open positions",
    r"not eligible",
    r"account (?:is )?(?:not|in)eligible",
    r"restricted (?:jurisdiction|region|state)",
    r"geo(?:graphic)?[ -]?(?:blocked|restriction)",
    r"unauthorized (?:product|market|category)",
    r"kyc",
    r"permission denied",
    r"forbidden",
)
_STRUCTURAL_RE = re.compile("|".join(_STRUCTURAL_PATTERNS))

# Explicitly NOT structural, even though some contain words above. These are
# transient or per-order and must never disable a venue.
_TRANSIENT_PATTERNS = (
    r"insufficient (?:balance|funds)",
    r"rate limit",
    r"too many requests",
    r"deprecated_v1_order_endpoint",
    r"market (?:is )?closed",
    r"invalid price",
    r"transport failure",
)
_TRANSIENT_RE = re.compile("|".join(_TRANSIENT_PATTERNS))


def _normalise(raw: str) -> str:
    """Lowercase, and turn Kalshi's underscore-joined `code` into words.

    Kalshi returns the same sentence twice — once underscore-joined in `code`,
    once spaced in `message` — so normalising lets a single pattern match either
    and survives the body being truncated mid-`message`.
    """
    return (raw or "").replace("_", " ").lower()


def is_structural_rejection(raw_error: str) -> bool:
    """True if this error means "you may not trade this here", not "not now".

    Transient patterns are checked FIRST: `insufficient_balance` must never take
    a venue offline, and a narrow structural pattern is worth less than a
    reliable exemption for the errors that legitimately recur.
    """
    text = _normalise(raw_error)
    if not text:
        return False
    if _TRANSIENT_RE.search(text):
        return False
    return bool(_STRUCTURAL_RE.search(text))


def actionable_reason(raw_error: str, limit: int = 160) -> str:
    """A human reason that keeps the END of the venue's message.

    Every one of these messages puts the instruction last — "Check your email
    for more details" — and all three reporting surfaces truncated it off (the
    console at 80 chars, the trade log at 200, the daily digest at 110, which
    landed on "Check you..."). So when this must shorten, it elides the MIDDLE
    and keeps both ends.
    """
    raw = raw_error or ""
    code = ""
    try:
        parsed = json.loads(raw)
        err = parsed.get("error", parsed)
        code = err.get("code") or err.get("message") or ""
    except (ValueError, AttributeError, TypeError):
        m = re.search(r'"(?:code|message)"\s*:\s*"([^"]*)', raw)
        code = m.group(1) if m else raw
    code = str(code).replace("_", " ").strip()
    if not code:
        return "unknown"
    if len(code) <= limit:
        return code
    # The tail gets the larger share: the head is boilerplate ("Nevada
    # residents are not currently allowed to..."), the tail is the instruction.
    head = limit // 3
    tail = limit - head - 5
    return f"{code[:head]} ... {code[-tail:]}"


# ── Cache ────────────────────────────────────────────────────────────────────
# Shape: {"kalshi:sports": {status, checked_at, reason, raw_error}, ...}
# Keyed on venue+PRODUCT, not venue: the observed block covers Sports, Elections
# and Entertainment specifically, so an account barred from sports may still
# trade crypto or weather. Disabling all of Kalshi would be over-broad even
# though sports is currently the whole book.

_PRODUCT_BY_CATEGORY = {
    "game": "sports", "spread": "sports", "total": "sports",
    "player_prop": "sports", "esports": "sports",
    "futures": "sports", "outrights": "sports", "championship": "sports",
    "crypto": "prediction", "weather": "prediction", "spx": "prediction",
    "mentions": "prediction", "companies": "prediction",
    "politics": "elections",
}


def product_for(category: str | None) -> str:
    """Map a scanner category to the venue's product bucket."""
    return _PRODUCT_BY_CATEGORY.get((category or "").strip().lower(), "sports")


def _key(venue: str, product: str) -> str:
    return f"{venue}:{product}"


def load() -> dict:
    try:
        return json.loads(ELIGIBILITY_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        # A missing or corrupt cache is `unknown`, which fails closed. That is
        # the safe direction and needs no special-casing by callers.
        return {}


def _save(cache: dict) -> None:
    try:
        ELIGIBILITY_PATH.parent.mkdir(parents=True, exist_ok=True)
        ELIGIBILITY_PATH.write_text(json.dumps(cache, indent=2), encoding="utf-8")
    except OSError:
        # Never let a cache write failure abort a trading run. The consequence
        # of not persisting is another `unknown`, i.e. more caution.
        pass


def status(venue: str, product: str, now: datetime | None = None) -> tuple[str, str]:
    """Return `(status, reason)` where status is ok | blocked | unknown.

    An `ok` older than `ELIGIBILITY_TTL_DAYS` decays to `unknown` — a verdict
    that never expires is how the 08-20 block went unnoticed for six days.
    A `blocked` NEVER decays: it is cleared only by an explicit probe or a real
    fill, because time passing is not evidence that a restriction was lifted.
    """
    entry = load().get(_key(venue, product))
    if not entry:
        return "unknown", "never verified"

    st = entry.get("status", "unknown")
    if st == "blocked":
        return "blocked", entry.get("reason") or "venue rejected an order"
    if st != "ok":
        return "unknown", entry.get("reason") or "no verdict"

    checked = entry.get("checked_at") or ""
    try:
        ts = datetime.fromisoformat(checked.replace("Z", "+00:00"))
    except ValueError:
        return "unknown", "unparseable checked_at"
    age = (now or datetime.now(timezone.utc)) - ts
    if age > timedelta(days=ELIGIBILITY_TTL_DAYS):
        return "unknown", f"last verified {age.days}d ago (TTL {ELIGIBILITY_TTL_DAYS}d)"
    return "ok", f"verified {age.days}d ago"


def record_rejection(venue: str, product: str, raw_error: str,
                     now: datetime | None = None) -> bool:
    """Mark blocked if `raw_error` is structural. Returns True if it blocked.

    Stores the **full** raw body, not a truncated prefix — the trade log's
    200-char cap is what removed "Check your email for more details" from the
    only record that had it.
    """
    if not is_structural_rejection(raw_error):
        return False
    cache = load()
    cache[_key(venue, product)] = {
        "status": "blocked",
        "checked_at": (now or datetime.now(timezone.utc)).isoformat(),
        "reason": actionable_reason(raw_error),
        "raw_error": raw_error,
    }
    _save(cache)
    return True


def record_success(venue: str, product: str, evidence: str = "order accepted",
                   now: datetime | None = None) -> None:
    """Mark eligible. Call ONLY on a real venue acceptance.

    A successful order is the only self-clearing path, and it is sound: the
    venue just did the thing it was refusing to do. Note a dry-run
    (`dry_run_blocked`) never reaches here — it proves nothing about
    eligibility.
    """
    cache = load()
    cache[_key(venue, product)] = {
        "status": "ok",
        "checked_at": (now or datetime.now(timezone.utc)).isoformat(),
        "reason": evidence,
    }
    _save(cache)


def clear(venue: str, product: str) -> None:
    """Drop a verdict, returning the pair to `unknown` (which fails closed)."""
    cache = load()
    cache.pop(_key(venue, product), None)
    _save(cache)


def _demo() -> None:
    """Self-check: the real 08-20 body, and the errors that must NOT disable."""
    real = ('{"error":{"code":"Nevada_residents_are_not_currently_allowed_to_open_'
            'positions_in_Sports,_Elections_and_Entertainment._Check_your_email_'
            'for_more_details.","message":"Nevada residents are not currently')
    assert is_structural_rejection(real)
    # Survives the trade log's truncation, because `code` alone matches.
    assert is_structural_rejection(real[:120])
    # The instruction at the tail is preserved even when shortened.
    assert "Check your email" in actionable_reason(real)
    # At a tight limit the head is sacrificed, never the instruction.
    assert actionable_reason(real, limit=60).endswith("details.")
    assert "email" in actionable_reason(real, limit=60)

    for benign in (
        '{"error":{"code":"insufficient_balance","message":"Insufficient balance"}}',
        '{"error":{"code":"deprecated_v1_order_endpoint"}}',
        '{"error":{"code":"rate_limit_exceeded"}}',
        "transport failure (placement UNKNOWN — reconcile): timeout",
        "", None,
    ):
        assert not is_structural_rejection(benign), benign

    assert product_for("game") == "sports"
    assert product_for("futures") == "sports"
    assert product_for("crypto") == "prediction"
    assert product_for("politics") == "elections"
    assert product_for(None) == "sports"
    print("venue_eligibility self-check OK")


if __name__ == "__main__":
    _demo()
