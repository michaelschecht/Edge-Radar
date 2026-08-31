"""Meta-tests: keep the suite from rotting as the wall clock moves.

A Kalshi ticker embeds its event date, and several gates read it against
`datetime.now()` -- Gate 4.8 (`is_game_started`) and Gate 3.7 (`days_to_event`).
So a fixture ticker written with a real near-term date is a time bomb: the test
passes the day it is written and starts failing on a date nobody chose.

It has gone off three times. S1 (2026-08-26) broke four tests by freezing NFL,
S5 broke 126 by enabling the time-to-event cap, and on 2026-08-27
`KXMLBGAME-26AUG271900NYYBOS-NYY` drifted into the past and took five
`test_exposure_gate` tests with it -- discovered a week later, during an
unrelated review, in a suite everyone had learned to read as "5 known failures".

The repo already has both correct idioms; this file just makes them mandatory:

  * an absolute date that must never arrive  -> year 99 (`KXMLBGAME-99AUG27...`)
  * an absolute date that must always be past -> year 20 (`KXMLBGAME-20JUN01...`)
  * anything relative to today -> mint it, as `test_time_to_event_gate._ticker`
    and `test_edge_detection._fresh_lu` do

The 90-day margin means a fixture is flagged a quarter before it detonates,
rather than on the morning it does.
"""

import re
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pytest

TESTS_DIR = Path(__file__).parent

# KXNFLGAME-26SEP13MIALV-MIA      -> date only, no start time
# KXMLBGAME-26AUG271900NYYBOS-NYY -> date + HHMM, readable as in-progress
TICKER_RE = re.compile(
    r"KX[A-Z]+-(\d{2})(JAN|FEB|MAR|APR|MAY|JUN|JUL|AUG|SEP|OCT|NOV|DEC)(\d{2})(\d{4})?"
)
MONTHS = {m: i + 1 for i, m in enumerate(
    ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
)}
SAFETY_MARGIN_DAYS = 90


def _iter_fixture_tickers():
    """Yield (path, lineno, ticker, embedded_date, has_start_time)."""
    for path in sorted(TESTS_DIR.glob("*.py")):
        if path.name == Path(__file__).name:
            continue        # this file names example tickers in its own prose
        for lineno, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
            for m in TICKER_RE.finditer(line):
                yy, mon, dd, hhmm = m.groups()
                try:
                    when = datetime(2000 + int(yy), MONTHS[mon], int(dd),
                                    tzinfo=timezone.utc)
                except ValueError:
                    continue        # e.g. FEB30, a deliberate unparseable fixture
                yield path.name, lineno, m.group(0), when, hhmm is not None


def test_no_fixture_ticker_is_about_to_rot():
    """No fixture ticker carrying a START TIME may sit within 90 days of today.

    Scoped deliberately to tickers with an embedded HHMM, because those are the
    only ones `is_game_started` acts on -- it returns False for a date-only
    ticker rather than guess an unknown kickoff. So `KXNFLSPREAD-26SEP13BALIND`
    is harmless however long it sits there, while `KXMLBGAME-26AUG271900NYYBOS`
    silently flipped Gate 4.8 the moment 7pm on the 27th passed.

    Widening this to every dated ticker flags ~50 fixtures that cannot affect a
    verdict (`test_ticker_display` in particular passes explicit `now=` values
    and *needs* real dates). A check that cries wolf gets deleted, so it covers
    exactly the shape that has actually broken the suite.

    Year 20 and year 99 tickers are the sanctioned escape hatches: both sit far
    outside the window, so they read the same way forever.
    """
    now = datetime.now(timezone.utc)
    horizon = now + timedelta(days=SAFETY_MARGIN_DAYS)

    # Forward-looking only: the bomb is a ticker that passes TODAY and fails on
    # a date nobody chose. A ticker already in the past has either broken the
    # suite (and been fixed) or provably cannot reach a gate -- the suite is
    # green with several such fixtures in `test_ticker_display`, which pass an
    # explicit `now=` and would break if their years were rewritten.
    offenders = [
        (f, ln, t, when.date())
        for f, ln, t, when, has_time in _iter_fixture_tickers()
        if has_time and now <= when <= horizon
    ]
    assert not offenders, (
        "Fixture tickers carrying a live date (within "
        f"{SAFETY_MARGIN_DAYS} days of {now.date()}) -- these will change a "
        "gate's verdict as the clock moves:\n"
        + "\n".join(f"  {f}:{ln}  {t}  (event {d})" for f, ln, t, d in offenders)
        + "\n\nUse year 99 for 'never arrives', year 20 for 'always past', or "
          "mint the ticker relative to now (see test_time_to_event_gate._ticker)."
    )


def test_started_ticker_idiom_actually_reads_as_started():
    """The year-20 escape hatch must genuinely trip Gate 4.8, now and forever."""
    from ticker_display import is_game_started
    assert is_game_started("KXMLBGAME-20JUN011840CWSMIA-MIA") is True


def test_upcoming_ticker_idiom_never_reads_as_started():
    """The year-99 escape hatch must never trip it."""
    from ticker_display import is_game_started
    assert is_game_started("KXMLBGAME-99JUN011840CWSMIA-MIA") is False
    assert is_game_started("KXMLBGAME-99AUG271900NYYBOS-NYY") is False


@pytest.mark.parametrize("ticker", [
    "KXNFLGAME-26SEP13MIALV-MIA",        # date only, no HHMM
    "KXNFLSPREAD-26SEP13BALIND-IND5",
])
def test_date_only_tickers_never_trip_the_live_gate(ticker):
    """Documents why the Sept-13 NFL fixtures are NOT time bombs for Gate 4.8.

    `is_game_started` deliberately returns False when a ticker carries no start
    time, rather than guessing. So date-only tickers are safe from Gate 4.8 (they
    are still measured by Gate 3.7, which conftest neutralises).
    """
    from ticker_display import is_game_started
    assert is_game_started(ticker) is False
