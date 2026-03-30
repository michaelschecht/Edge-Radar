"""Tests for ticker_display.py — ticker parsing, date extraction, filtering."""

from datetime import date, timedelta
from unittest.mock import patch

import pytest

from ticker_display import (
    _split_team_codes,
    parse_game_datetime,
    parse_matchup,
    parse_pick_team,
    format_bet_label,
    extract_ticker_date,
    resolve_date_arg,
    filter_by_date,
    filter_exclude_tickers,
    TEAM_NAMES,
)
from opportunity import Opportunity


# ── _split_team_codes ────────────────────────────────────────────────────────

class TestSplitTeamCodes:
    def test_two_three_char_teams(self):
        assert _split_team_codes("CWSMIA") == ("CWS", "MIA")

    def test_three_three_char_teams(self):
        assert _split_team_codes("NYYBOS") == ("NYY", "BOS")

    def test_two_char_away(self):
        assert _split_team_codes("TBMIL") == ("TB", "MIL")

    def test_two_char_home(self):
        assert _split_team_codes("MINKC") == ("MIN", "KC")

    def test_three_two_char_teams(self):
        assert _split_team_codes("NYMKC") == ("NYM", "KC")

    def test_unknown_returns_combined(self):
        away, home = _split_team_codes("XYZABC")
        assert (away, home) == ("XYZABC", "")


# ── parse_game_datetime ──────────────────────────────────────────────────────

class TestParseGameDatetime:
    def test_mlb_game_ticker(self):
        result = parse_game_datetime("KXMLBGAME-26MAR301840CWSMIA-MIA")
        assert result == "Mar 30 6:40pm"

    def test_nba_game_ticker(self):
        result = parse_game_datetime("KXNBAGAME-26MAR302000LALBOS-LAL")
        assert result == "Mar 30 8:00pm"

    def test_morning_time(self):
        result = parse_game_datetime("KXMLBGAME-26APR011010BOSNYY-BOS")
        assert result == "Apr 1 10:10am"

    def test_spread_ticker(self):
        result = parse_game_datetime("KXNCAAMBSPREAD-26MAR221900UCLACONN-5")
        assert result == "Mar 22 7:00pm"

    def test_total_ticker(self):
        result = parse_game_datetime("KXNCAAMBTOTAL-26MAR251930NEVAUB-150")
        assert result == "Mar 25 7:30pm"

    def test_prediction_ticker_date_only(self):
        result = parse_game_datetime("KXBTC-26MAR28-T88000")
        assert result == "Mar 28"

    def test_unparseable_returns_empty(self):
        assert parse_game_datetime("RANDOM-TICKER") == ""

    def test_noon(self):
        result = parse_game_datetime("KXMLBGAME-26JUL041200NYMMIA-NYM")
        assert result == "Jul 4 12:00pm"

    def test_midnight(self):
        result = parse_game_datetime("KXMLBGAME-26JUL040000NYMMIA-NYM")
        assert result == "Jul 4 12:00am"


# ── parse_matchup ────────────────────────────────────────────────────────────

class TestParseMatchup:
    def test_mlb_matchup(self):
        assert parse_matchup("KXMLBGAME-26MAR301840CWSMIA-MIA") == "White Sox @ Miami"

    def test_two_char_away(self):
        result = parse_matchup("KXMLBGAME-26MAR301940TBMIL-TB")
        assert result == "Tampa Bay @ Milwaukee"

    def test_non_game_returns_empty(self):
        assert parse_matchup("KXBTC-26MAR28-T88000") == ""


# ── parse_pick_team ──────────────────────────────────────────────────────────

class TestParsePickTeam:
    def test_known_team(self):
        assert parse_pick_team("KXMLBGAME-26MAR301840CWSMIA-MIA") == "Miami"

    def test_unknown_suffix(self):
        result = parse_pick_team("KXMLBGAME-26MAR301840CWSMIA-5")
        assert result == "5"  # numeric strike, returned as-is

    def test_no_hyphen(self):
        assert parse_pick_team("NOTICKER") == ""


# ── format_bet_label ─────────────────────────────────────────────────────────

class TestFormatBetLabel:
    def test_game_ticker_uses_matchup(self):
        result = format_bet_label("KXMLBGAME-26MAR301840CWSMIA-MIA", "Some Title")
        assert "White Sox" in result
        assert "Miami" in result

    def test_non_game_uses_title(self):
        result = format_bet_label("KXBTC-26MAR28-T88000", "Bitcoin > $88,000?")
        assert "Bitcoin" in result


# ── extract_ticker_date ──────────────────────────────────────────────────────

class TestExtractTickerDate:
    def test_mlb_game(self):
        assert extract_ticker_date("KXMLBGAME-26MAR301840CWSMIA-MIA") == "2026-03-30"

    def test_prediction(self):
        assert extract_ticker_date("KXBTC-26MAR28-T88000") == "2026-03-28"

    def test_april(self):
        assert extract_ticker_date("KXMLBGAME-26APR011010BOSNYY-BOS") == "2026-04-01"

    def test_unparseable(self):
        assert extract_ticker_date("RANDOM") is None


# ── resolve_date_arg ─────────────────────────────────────────────────────────

class TestResolveDateArg:
    def test_today(self):
        assert resolve_date_arg("today") == date.today().isoformat()

    def test_tomorrow(self):
        assert resolve_date_arg("tomorrow") == (date.today() + timedelta(days=1)).isoformat()

    def test_iso_format(self):
        assert resolve_date_arg("2026-03-31") == "2026-03-31"

    def test_month_day(self):
        result = resolve_date_arg("03-31")
        assert result.endswith("-03-31")

    def test_short_month(self):
        result = resolve_date_arg("mar31")
        assert result.endswith("-03-31")

    def test_case_insensitive(self):
        result = resolve_date_arg("MAR31")
        assert result.endswith("-03-31")


# ── filter_by_date ───────────────────────────────────────────────────────────

class TestFilterByDate:
    def test_filters_to_matching_date(self):
        opps = [
            Opportunity("KXMLBGAME-26MAR301840CWSMIA-MIA", "G1", "game", "yes",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
            Opportunity("KXMLBGAME-26MAR311840PITCIN-PIT", "G2", "game", "yes",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
        ]
        result = filter_by_date(opps, "2026-03-30")
        assert len(result) == 1
        assert result[0].ticker.endswith("MIA")

    def test_no_matches_returns_empty(self):
        opps = [
            Opportunity("KXMLBGAME-26MAR301840CWSMIA-MIA", "G1", "game", "yes",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
        ]
        assert filter_by_date(opps, "2026-04-15") == []

    def test_works_with_dicts(self):
        opps = [{"ticker": "KXMLBGAME-26MAR301840CWSMIA-MIA"}]
        result = filter_by_date(opps, "2026-03-30")
        assert len(result) == 1


# ── filter_exclude_tickers ───────────────────────────────────────────────────

class TestFilterExcludeTickers:
    def test_excludes_matching_event(self):
        opps = [
            Opportunity("KXMLBGAME-26MAR301840CWSMIA-MIA", "G1", "game", "yes",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
            Opportunity("KXMLBGAME-26MAR311840PITCIN-PIT", "G2", "game", "yes",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
        ]
        # Holding YES on MIA — should exclude the NO side too
        exclude = {"KXMLBGAME-26MAR301840CWSMIA-MIA"}
        result = filter_exclude_tickers(opps, exclude)
        assert len(result) == 1
        assert "PITCIN" in result[0].ticker

    def test_excludes_opposite_side_of_same_game(self):
        opps = [
            Opportunity("KXMLBGAME-26MAR301840CWSMIA-CWS", "G1", "game", "no",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
        ]
        # Holding YES on MIA — should also exclude CWS side of same game
        exclude = {"KXMLBGAME-26MAR301840CWSMIA-MIA"}
        result = filter_exclude_tickers(opps, exclude)
        assert len(result) == 0

    def test_keeps_unrelated_games(self):
        opps = [
            Opportunity("KXMLBGAME-26MAR311840PITCIN-PIT", "G2", "game", "yes",
                        0.5, 0.6, 0.1, "test", "high", 8.0, 8.0, {}),
        ]
        exclude = {"KXMLBGAME-26MAR301840CWSMIA-MIA"}
        result = filter_exclude_tickers(opps, exclude)
        assert len(result) == 1
