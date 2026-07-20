"""Tests for `betting_analysis.py` render helpers.

Regression coverage for the longshot table crashing on settlement records
that are missing `edge_estimated` / `fair_value` (the trade ledger already
guards these; the longshot table did not — see 2026-07-14 repo review #3).
"""

from datetime import datetime, timezone

import betting_analysis


def _longshot_row(**overrides):
    row = {
        "_ts": datetime(2026, 7, 20, 19, 40, tzinfo=timezone.utc),
        "ticker": "KXMLBGAME-26JUL20SFKC-KC",
        "side": "yes",
        "market_price_at_entry": 0.10,  # < 0.15 → qualifies as a longshot
        "edge_estimated": 0.05,
        "fair_value": 0.15,
        "won": False,
        "net_pnl": -1.0,
    }
    row.update(overrides)
    return row


class TestRenderLongshotNoneGuard:
    def test_missing_edge_and_fair_value_does_not_crash(self):
        rows = [_longshot_row(edge_estimated=None, fair_value=None)]
        out = "\n".join(betting_analysis._render_longshot(rows))
        # renders the row with placeholders instead of raising TypeError
        assert "—" in out
        assert "10¢" in out  # price still renders (it's the filter key, never None)

    def test_present_values_still_render_numerically(self):
        rows = [_longshot_row()]
        out = "\n".join(betting_analysis._render_longshot(rows))
        assert "+5.0%" in out
        assert "15%" in out

    def test_one_bad_row_does_not_kill_the_others(self):
        rows = [
            _longshot_row(edge_estimated=None, fair_value=None),
            _longshot_row(),
        ]
        out = "\n".join(betting_analysis._render_longshot(rows))
        assert "+5.0%" in out  # the good row survived
        assert "—" in out      # the bad row rendered a placeholder
