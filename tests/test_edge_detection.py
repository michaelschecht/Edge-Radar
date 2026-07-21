"""Tests for edge detection math — normal CDF models and de-vigging."""

from unittest.mock import MagicMock, patch

import os
import json
import time
from datetime import datetime, timezone

import pytest
from scipy.stats import norm

from edge_detector import (
    CATEGORY_MAP,
    KALSHI_TO_ODDS_SPORT,
    SPORT_MARGIN_STDEV,
    SPORT_TOTAL_STDEV,
    _adjust_confidence_with_stats,
    _get_margin_stdev,
    _get_total_stdev,
    _match_team_outcome,
    _team_match_strength,
    consensus_fair_value,
    consensus_spread_prob,
    consensus_total_prob,
    detect_edge_game,
    extract_event_teams,
    find_market_event,
)
from futures_edge import devig_nway, FUTURES_MAP


# ── devig_nway ───────────────────────────────────────────────────────────────

class TestDevigNway:
    def test_two_way_even(self):
        outcomes = [
            {"name": "Team A", "price": 2.0},
            {"name": "Team B", "price": 2.0},
        ]
        result = devig_nway(outcomes)
        assert abs(result["Team A"] - 0.5) < 0.001
        assert abs(result["Team B"] - 0.5) < 0.001

    def test_two_way_favorite(self):
        outcomes = [
            {"name": "Favorite", "price": 1.5},  # implied 66.7%
            {"name": "Underdog", "price": 3.0},   # implied 33.3%
        ]
        result = devig_nway(outcomes)
        # Total implied = 1.0 (no vig in this case)
        assert abs(result["Favorite"] - 0.667) < 0.01
        assert abs(result["Underdog"] - 0.333) < 0.01

    def test_two_way_with_vig(self):
        # Typical -110 / -110 line: 1.909 / 1.909
        outcomes = [
            {"name": "Home", "price": 1.909},
            {"name": "Away", "price": 1.909},
        ]
        result = devig_nway(outcomes)
        # Each implied ~52.4%, total ~104.8%, devigged each ~50%
        assert abs(result["Home"] - 0.5) < 0.01
        assert abs(result["Away"] - 0.5) < 0.01

    def test_nway_sums_to_one(self):
        outcomes = [
            {"name": "A", "price": 5.0},
            {"name": "B", "price": 3.0},
            {"name": "C", "price": 4.0},
            {"name": "D", "price": 10.0},
        ]
        result = devig_nway(outcomes)
        total = sum(result.values())
        assert abs(total - 1.0) < 0.001

    def test_empty_outcomes(self):
        assert devig_nway([]) == {}

    def test_heavy_favorite(self):
        # Very low price (heavy favorite) — implied ~91%
        outcomes = [
            {"name": "Sure Thing", "price": 1.1},
            {"name": "No Chance", "price": 10.0},
        ]
        result = devig_nway(outcomes)
        assert result["Sure Thing"] > 0.85

    def test_price_below_one_skipped(self):
        # Prices <= 1.0 should be handled gracefully
        outcomes = [
            {"name": "A", "price": 0.5},  # invalid
            {"name": "B", "price": 2.0},
        ]
        result = devig_nway(outcomes)
        # Only B has valid odds
        assert "B" in result


# ── R22: futures ticker-to-series matching (no prefix collision) ─────────────

class TestFuturesSeriesMatch:
    """R22 (2026-04-24): `FUTURES_MAP` is now keyed by exact series (everything
    before the first hyphen in the ticker). Old `ticker.startswith(prefix)`
    logic had two bugs: (1) prefix collision — KXMLBPLAYOFFS-26-LAD matched
    the KXMLB entry because startswith checked from the front, (2) even if
    resolved, KXMLBPLAYOFFS was mapped to World Series winner odds but
    represents playoff qualification — a different question. LAD is ~95% to
    make playoffs but ~28% to win the WS, so championship odds produced
    garbage "+60-75% edge" NO-favorite recommendations. Fix: exact series
    match + remove the 5 semantically-wrong entries. Unmapped series are
    skipped silently (see `scan_futures_markets` loop).
    """

    def test_kxmlb_maps_to_world_series(self):
        series = "KXMLB-26-LAD".split("-", 1)[0]
        assert series == "KXMLB"
        assert FUTURES_MAP[series][2] == "MLB World Series Champion"

    def test_kxmlbplayoffs_no_longer_maps(self):
        # KXMLBPLAYOFFS was removed to avoid priced-against-wrong-odds bug.
        assert "KXMLBPLAYOFFS" not in FUTURES_MAP

    def test_kxmlbplayoffs_ticker_does_not_collide_with_kxmlb(self):
        # Exact-series match: "KXMLBPLAYOFFS" != "KXMLB" even though the
        # old startswith logic would have matched KXMLB first.
        series = "KXMLBPLAYOFFS-26-LAD".split("-", 1)[0]
        assert series == "KXMLBPLAYOFFS"
        assert series not in FUTURES_MAP  # silently skipped by scanner

    def test_nba_conferences_no_longer_map(self):
        assert "KXNBAEAST" not in FUTURES_MAP
        assert "KXNBAWEST" not in FUTURES_MAP

    def test_nhl_conferences_no_longer_map(self):
        assert "KXNHLEAST" not in FUTURES_MAP
        assert "KXNHLWEST" not in FUTURES_MAP

    def test_nba_conference_ticker_does_not_collide_with_kxnba(self):
        series = "KXNBAEAST-26-BOS".split("-", 1)[0]
        assert series == "KXNBAEAST"
        assert series not in FUTURES_MAP

    def test_valid_series_still_resolve(self):
        # All non-removed entries still map to the right label
        assert FUTURES_MAP["KXSB"][2] == "NFL Super Bowl Champion"
        assert FUTURES_MAP["KXNBA"][2] == "NBA Finals Champion"
        assert FUTURES_MAP["KXNHL"][2] == "NHL Stanley Cup Champion"
        assert FUTURES_MAP["KXPGATOUR"][2] == "PGA Tour Major Winner"


# ── PGA: resolve the major from the market title (Odds API majors-only) ──────

class TestGolfMajorResolution:
    """KXPGATOUR spans the whole PGA Tour, but The Odds API only publishes
    outright fields for the 4 majors. `_golf_major_key` maps a market title to
    the right major's odds key, skipping weekly stops and qualifiers so they're
    never priced against the wrong (or absent) field.
    """

    def test_us_open_resolves(self):
        from futures_edge import _golf_major_key
        key, label = _golf_major_key("Will Bud Cauley win the U.S. Open?")
        assert key == "golf_us_open_winner"
        assert label == "U.S. Open Winner"

    def test_pga_championship_resolves(self):
        from futures_edge import _golf_major_key
        key, _ = _golf_major_key("Will Tom Hoge win the PGA Championship?")
        assert key == "golf_pga_championship_winner"

    def test_masters_resolves(self):
        from futures_edge import _golf_major_key
        key, _ = _golf_major_key("Will X win the Masters?")
        assert key == "golf_masters_tournament_winner"

    def test_the_open_resolves(self):
        from futures_edge import _golf_major_key
        key, _ = _golf_major_key("Will X win The Open?")
        assert key == "golf_the_open_championship_winner"

    def test_qualifier_is_skipped(self):
        # "U.S. Open Final Qualifying ..." contains "u.s. open" but is NOT the
        # major — must return None so it isn't priced against U.S. Open odds.
        from futures_edge import _golf_major_key
        assert _golf_major_key(
            "Will Kevin Streelman win the U.S. Open Final Qualifying Dallas Playoff?"
        ) is None

    def test_canadian_open_not_mistaken_for_the_open(self):
        # Bare "open" must not match The Open Championship.
        from futures_edge import _golf_major_key
        assert _golf_major_key("Will Ben Kohles win the RBC Canadian Open?") is None

    def test_weekly_stop_is_skipped(self):
        from futures_edge import _golf_major_key
        assert _golf_major_key("Will Marco Penge win the RBC Heritage?") is None


# ── R13: confidence bumps are one-way (down only) ───────────────────────────

class TestConfidenceBumpsOneWay:
    """R13 (2026-04-24): `_adjust_confidence_with_stats` should drop a level
    on `contradicts`, but treat `supports` as a no-op. 30-day calibration
    showed High-confidence WR (47%) below Medium (53%); upward bumps were
    correlated with inflated claimed edge, not better outcomes.
    """

    def test_supports_is_no_op_at_each_tier(self):
        signal = {"stats_found": True, "signal": "supports"}
        assert _adjust_confidence_with_stats("low", signal) == "low"
        assert _adjust_confidence_with_stats("medium", signal) == "medium"
        assert _adjust_confidence_with_stats("high", signal) == "high"

    def test_contradicts_drops_one_level(self):
        signal = {"stats_found": True, "signal": "contradicts"}
        assert _adjust_confidence_with_stats("high", signal) == "medium"
        assert _adjust_confidence_with_stats("medium", signal) == "low"
        assert _adjust_confidence_with_stats("low", signal) == "low"  # clamp

    def test_neutral_is_no_op(self):
        signal = {"stats_found": True, "signal": "neutral"}
        assert _adjust_confidence_with_stats("medium", signal) == "medium"

    def test_stats_not_found_is_no_op(self):
        assert _adjust_confidence_with_stats("medium", {"stats_found": False}) == "medium"
        assert _adjust_confidence_with_stats("high", {}) == "high"


# ── Normal CDF spread model (math validation) ───────────────────────────────

class TestSpreadMath:
    """Validate the normal CDF model used for spread probability.

    The actual function (consensus_spread_prob) requires API data,
    so we test the underlying math directly.
    """

    def test_even_spread_gives_fifty_percent(self):
        # If book spread = 0 and implied = 50%, mean margin = 0
        # P(margin > 0) should be ~50%
        stdev = SPORT_MARGIN_STDEV["basketball_nba"]
        mean_margin = 0.0
        prob = 1 - norm.cdf(0, loc=mean_margin, scale=stdev)
        assert abs(prob - 0.5) < 0.001

    def test_favorite_covers_large_spread(self):
        # Team favored by 10, but Kalshi strike is -3 (easier to cover)
        stdev = SPORT_MARGIN_STDEV["basketball_nba"]
        mean_margin = 10.0  # expected to win by 10
        strike = -3.0
        prob = 1 - norm.cdf(strike, loc=mean_margin, scale=stdev)
        assert prob > 0.75

    def test_underdog_covers_tough_spread(self):
        # Underdog (mean margin -5), strike is +7 (very hard to cover)
        stdev = SPORT_MARGIN_STDEV["basketball_nba"]
        mean_margin = -5.0
        strike = 7.0
        prob = 1 - norm.cdf(strike, loc=mean_margin, scale=stdev)
        assert prob < 0.20

    def test_mlb_lower_variance(self):
        # MLB has much tighter margins than NBA — same mean/strike should
        # produce a more extreme probability under MLB variance.
        stdev_mlb = SPORT_MARGIN_STDEV["baseball_mlb"]
        stdev_nba = SPORT_MARGIN_STDEV["basketball_nba"]
        mean = 2.0
        strike = 0.0

        prob_mlb = 1 - norm.cdf(strike, loc=mean, scale=stdev_mlb)
        prob_nba = 1 - norm.cdf(strike, loc=mean, scale=stdev_nba)

        # MLB should be more confident (less variance)
        assert prob_mlb > prob_nba


class TestSportStdevValues:
    """R2 (2026-04-21): per-sport stdev bump for NBA/NCAAB/MLB.

    NHL was intentionally left untouched (+87% ROI in 14-day review)."""

    def test_r2_margin_values(self):
        # NBA +15%: 12.0 -> 13.8
        assert SPORT_MARGIN_STDEV["basketball_nba"] == pytest.approx(13.8)
        # NCAAB +10%: 11.0 -> 12.1
        assert SPORT_MARGIN_STDEV["basketball_ncaab"] == pytest.approx(12.1)
        # MLB +15%: 3.5 -> 4.025
        assert SPORT_MARGIN_STDEV["baseball_mlb"] == pytest.approx(4.025)

    def test_r2_total_values(self):
        assert SPORT_TOTAL_STDEV["basketball_nba"] == pytest.approx(20.7)
        assert SPORT_TOTAL_STDEV["basketball_ncaab"] == pytest.approx(17.6)
        assert SPORT_TOTAL_STDEV["baseball_mlb"] == pytest.approx(3.45)

    def test_nhl_untouched(self):
        # NHL explicitly excluded from R2 — well-calibrated in 14-day review.
        assert SPORT_MARGIN_STDEV["icehockey_nhl"] == 2.5
        assert SPORT_TOTAL_STDEV["icehockey_nhl"] == 2.2

    def test_nfl_ncaaf_soccer_mma_untouched(self):
        # R2 only names NBA/NCAAB/MLB. Other sports unchanged.
        assert SPORT_MARGIN_STDEV["americanfootball_nfl"] == 13.5
        assert SPORT_MARGIN_STDEV["americanfootball_ncaaf"] == 15.0
        assert SPORT_MARGIN_STDEV["soccer"] == 1.8
        assert SPORT_MARGIN_STDEV["mma"] == 5.0

    def test_ticker_prefix_lookup_margin(self):
        assert _get_margin_stdev("KXNBAGAME-26APR21LALBOS-LAL") == 13.8
        assert _get_margin_stdev("KXNCAAMBSPREAD-26APR21UCLACONN-UCLA") == 12.1
        assert _get_margin_stdev("KXMLBGAME-26APR21NYYKAC-NYY") == 4.025
        assert _get_margin_stdev("KXNHLGAME-26APR21TORBOS-TOR") == 2.5

    def test_ticker_prefix_lookup_total(self):
        assert _get_total_stdev("KXNBATOTAL-26APR21LALBOS-T220") == 20.7
        assert _get_total_stdev("KXNCAAMBTOTAL-26APR21UCLACONN-T150") == 17.6
        assert _get_total_stdev("KXMLBTOTAL-26APR21NYYKAC-T8") == 3.45
        assert _get_total_stdev("KXNHLTOTAL-26APR21TORBOS-T6") == 2.2


class TestTotalMath:
    """Validate the normal CDF model for over/under totals."""

    def test_over_at_median_is_fifty(self):
        stdev = SPORT_TOTAL_STDEV["basketball_nba"]
        expected_total = 220.0
        strike = 220.0
        prob_over = 1 - norm.cdf(strike, loc=expected_total, scale=stdev)
        assert abs(prob_over - 0.5) < 0.001

    def test_over_well_below_expected(self):
        # Strike well below expected total — high over probability
        stdev = SPORT_TOTAL_STDEV["basketball_nba"]
        expected_total = 240.0
        strike = 210.0
        prob_over = 1 - norm.cdf(strike, loc=expected_total, scale=stdev)
        assert prob_over > 0.85

    def test_over_well_above_expected(self):
        # Strike well above expected total — low over probability
        stdev = SPORT_TOTAL_STDEV["basketball_nba"]
        expected_total = 210.0
        strike = 240.0
        prob_over = 1 - norm.cdf(strike, loc=expected_total, scale=stdev)
        assert prob_over < 0.15


# ── fetch_odds_api key-rotation ──────────────────────────────────────────────

class TestFetchOddsApiKeyRotation:
    """Regression for the silent-0-events bug where range(3) bailed before
    trying the last rotated key. A single-sport scan must rotate through every
    configured key before returning empty."""

    def _mock_response(self, status_code: int, json_data=None) -> MagicMock:
        resp = MagicMock()
        resp.status_code = status_code
        resp.json.return_value = json_data if json_data is not None else []
        resp.headers = {"x-requests-remaining": "100"}
        resp.raise_for_status = MagicMock()
        if status_code >= 400 and status_code not in (401, 429):
            resp.raise_for_status.side_effect = Exception(f"HTTP {status_code}")
        return resp

    @pytest.fixture(autouse=True)
    def _isolate_quota_cache(self, tmp_path, monkeypatch):
        """Redirect the odds_api on-disk quota cache and the odds_cache
        file-backed response cache to a tmpdir so test calls neither clobber
        real keys nor reuse responses across tests.
        """
        import odds_api
        import odds_cache
        monkeypatch.setattr(odds_api, "_QUOTA_CACHE_PATH", tmp_path / "quota.json")
        monkeypatch.setattr(odds_cache, "_CACHE_DIR", tmp_path / "odds_cache")

    def _setup_keys(self, keys: list[str]) -> None:
        """Install a known key list into odds_api module state."""
        import odds_api
        odds_api._keys = list(keys)
        odds_api._current_index = 0
        odds_api._remaining = {}

    def test_tries_all_keys_before_giving_up(self):
        import edge_detector
        edge_detector._odds_cache.clear()
        self._setup_keys(["k1", "k2", "k3", "k4"])

        # All 4 keys return 401
        always_401 = self._mock_response(401)
        with patch("edge_detector.requests.get", return_value=always_401) as mock_get:
            result = edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")

        assert result == []
        # Each key should have been tried exactly once
        assert mock_get.call_count == 4
        used_keys = [call.kwargs["params"]["apiKey"] for call in mock_get.call_args_list]
        assert set(used_keys) == {"k1", "k2", "k3", "k4"}

    def test_succeeds_after_rotating_past_exhausted_keys(self):
        """Reproduces the user-reported bug: first 3 keys exhausted, 4th works."""
        import edge_detector
        edge_detector._odds_cache.clear()
        self._setup_keys(["k1", "k2", "k3", "k4"])

        responses = {
            "k1": self._mock_response(401),
            "k2": self._mock_response(401),
            "k3": self._mock_response(401),
            "k4": self._mock_response(200, [{"home_team": "Yankees", "away_team": "Red Sox"}]),
        }

        def side_effect(url, params=None, **kwargs):
            return responses[params["apiKey"]]

        with patch("edge_detector.requests.get", side_effect=side_effect):
            result = edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")

        assert len(result) == 1
        assert result[0]["home_team"] == "Yankees"

    def test_first_key_success_no_rotation(self):
        """Happy path: first key works, no unnecessary rotation."""
        import edge_detector
        edge_detector._odds_cache.clear()
        self._setup_keys(["k1", "k2"])

        ok = self._mock_response(200, [{"home_team": "Dodgers"}])
        with patch("edge_detector.requests.get", return_value=ok) as mock_get:
            result = edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")

        assert len(result) == 1
        assert mock_get.call_count == 1
        assert mock_get.call_args.kwargs["params"]["apiKey"] == "k1"

    def test_single_key_401_returns_empty(self):
        """One configured key that 401s — log and return [] without retrying."""
        import edge_detector
        edge_detector._odds_cache.clear()
        self._setup_keys(["only_key"])

        with patch("edge_detector.requests.get",
                   return_value=self._mock_response(401)) as mock_get:
            result = edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")

        assert result == []
        # Tried exactly once — no infinite loop on single-key rotation
        assert mock_get.call_count == 1


# ── In-process cache live-aware TTL (L1) ─────────────────────────────────────

class TestInProcessCacheTtl:
    """L1: the in-process `_odds_cache` now expires. Pre-game entries live for
    the full TTL (within-scan dedup preserved); in-play entries expire on the
    short live TTL so a long-running webapp refetches current odds."""

    def _mock_response(self, events: list) -> MagicMock:
        resp = MagicMock()
        resp.status_code = 200
        resp.json.return_value = events
        resp.headers = {"x-requests-remaining": "100"}
        resp.raise_for_status = MagicMock()
        return resp

    @pytest.fixture(autouse=True)
    def _isolate(self, tmp_path, monkeypatch):
        import odds_api
        import odds_cache
        import edge_detector
        # Disable the file cache so we isolate the in-process layer.
        monkeypatch.setattr(odds_api, "_QUOTA_CACHE_PATH", tmp_path / "quota.json")
        monkeypatch.setattr(odds_cache, "_CACHE_DIR", tmp_path / "odds_cache")
        from app.config import reset_config
        monkeypatch.setenv("ODDS_CACHE_ENABLED", "false")
        monkeypatch.setenv("ODDS_CACHE_TTL_SECONDS", "300")
        monkeypatch.setenv("ODDS_LIVE_TTL_SECONDS", "45")
        reset_config()
        odds_api._keys = ["k1"]
        odds_api._current_index = 0
        odds_api._remaining = {}
        edge_detector._odds_cache.clear()
        yield
        reset_config()

    def test_pregame_entry_dedups_within_ttl(self, monkeypatch):
        import edge_detector
        clock = [1000.0]
        monkeypatch.setattr(edge_detector.time, "monotonic", lambda: clock[0])
        upcoming = [{"home_team": "Yankees", "commence_time": "2099-01-01T00:00:00Z"}]

        with patch("edge_detector.requests.get",
                   return_value=self._mock_response(upcoming)) as mock_get:
            edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")
            clock[0] += 120  # 2 min later — still within 300s pre-game TTL
            edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")

        assert mock_get.call_count == 1  # second call served from cache

    def test_live_entry_expires_on_live_ttl(self, monkeypatch):
        import edge_detector
        clock = [1000.0]
        monkeypatch.setattr(edge_detector.time, "monotonic", lambda: clock[0])
        live = [{"home_team": "Yankees", "commence_time": "2020-01-01T00:00:00Z"}]

        with patch("edge_detector.requests.get",
                   return_value=self._mock_response(live)) as mock_get:
            edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")
            clock[0] += 60  # 60s later — past the 45s live TTL
            edge_detector.fetch_odds_api("baseball_mlb", markets="h2h")

        assert mock_get.call_count == 2  # in-play entry refetched


# ── Opponent-validated event matching (fix A + B) ─────────────────────────────

# Real Odds API responses always carry a per-bookmaker last_update; fixtures must
# too, or the Phase-2 live-staleness guard excludes them whenever a fixture's
# commence_time happens to be in the past. Stamp "now" so books read as fresh.
def _fresh_lu():
    return datetime.now(timezone.utc).isoformat()


def _h2h_event(away, home, away_price, home_price, commence,
               books=("pinnacle", "draftkings")):
    """Build a minimal Odds API h2h event with N identical bookmakers."""
    return {
        "away_team": away,
        "home_team": home,
        "commence_time": commence,
        "bookmakers": [
            {
                "key": b,
                "last_update": _fresh_lu(),
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": away, "price": away_price},
                        {"name": home, "price": home_price},
                    ],
                }],
            }
            for b in books
        ],
    }


def _totals_event(away, home, line, over_price, commence, books=("pinnacle",)):
    return {
        "away_team": away,
        "home_team": home,
        "commence_time": commence,
        "bookmakers": [
            {
                "key": b,
                "last_update": _fresh_lu(),
                "markets": [{
                    "key": "totals",
                    "outcomes": [
                        {"name": "Over", "point": line, "price": over_price},
                        {"name": "Under", "point": line, "price": over_price},
                    ],
                }],
            }
            for b in books
        ],
    }


def _spread_event(favorite, underdog, fav_point, fav_price, dog_price,
                  commence, books=("pinnacle",)):
    """Odds API spreads event. fav_point is the favorite's handicap (negative,
    e.g. -1.5); the underdog gets +fav_point. Prices carry book vig."""
    return {
        "away_team": underdog,
        "home_team": favorite,
        "commence_time": commence,
        "bookmakers": [
            {
                "key": b,
                "last_update": _fresh_lu(),
                "markets": [{
                    "key": "spreads",
                    "outcomes": [
                        {"name": favorite, "point": fav_point, "price": fav_price},
                        {"name": underdog, "point": -fav_point, "price": dog_price},
                    ],
                }],
            }
            for b in books
        ],
    }


def _mlb_game_market(away, home, yes_team, ticker, yes_ask="0.54",
                     no_ask="0.48", yes_bid="0.52"):
    return {
        "ticker": ticker,
        "title": f"{away} vs {home} Winner?",
        "yes_sub_title": yes_team,
        "no_sub_title": yes_team,
        "rules_primary": (
            f"If {yes_team} wins the {away} vs {home} professional baseball "
            f"game originally scheduled for Jun 5, 2026, then the market "
            f"resolves to Yes."
        ),
        "yes_ask_dollars": yes_ask,
        "no_ask_dollars": no_ask,
        "yes_bid_dollars": yes_bid,
    }


class TestExtractEventTeams:
    def test_strips_totals_filler_prefix(self):
        # Totals rules read "the teams in the New York at San Antonio ..."
        m = {"rules_primary": (
            "If the teams in the New York at San Antonio professional "
            "basketball game originally scheduled for Jun 3, 2026 collectively "
            "score more than 232.5 points, then the market resolves to Yes.")}
        assert extract_event_teams(m) == ("New York", "San Antonio")

    def test_plain_vs_matchup(self):
        m = {"rules_primary": (
            "If Washington wins the Washington vs Arizona professional "
            "baseball game originally scheduled for Jun 5, 2026, then the "
            "market resolves to Yes.")}
        assert extract_event_teams(m) == ("Washington", "Arizona")

    def test_strips_playoff_game_prefix(self):
        # Playoff-series rules carry a "Game N:" prefix that leaked into the
        # team name and broke clean matching.
        m = {"rules_primary": (
            "If San Antonio wins the Game 3: San Antonio at New York "
            "professional basketball game originally scheduled for "
            "Jun 8, 2026, then the market resolves to Yes.")}
        assert extract_event_teams(m) == ("San Antonio", "New York")


class TestFindMarketEvent:
    """Fix A: a market may only be priced against the odds event that holds
    BOTH its teams. The contamination bug paired a market against any event a
    single team appeared in."""

    def test_absent_game_returns_none(self):
        # Kalshi market is Washington @ Arizona, but the only Arizona event in
        # the feed is Dodgers @ Arizona — must NOT match (the old bug).
        market = _mlb_game_market("Washington", "Arizona", "Arizona",
                                  "KXMLBGAME-26JUN052140WSHAZ-AZ")
        feed = [_h2h_event("Los Angeles Dodgers", "Arizona Diamondbacks",
                           1.6, 2.5, "2026-06-05T01:41:00Z")]
        assert find_market_event(market, feed) is None

    def test_matches_correct_event(self):
        market = _mlb_game_market("Washington", "Arizona", "Arizona",
                                  "KXMLBGAME-26JUN052140WSHAZ-AZ")
        wsh_az = _h2h_event("Washington Nationals", "Arizona Diamondbacks",
                            2.0, 1.85, "2026-06-06T01:40:00Z")
        feed = [
            _h2h_event("Los Angeles Dodgers", "Arizona Diamondbacks",
                       1.6, 2.5, "2026-06-05T01:41:00Z"),
            wsh_az,
        ]
        assert find_market_event(market, feed) is wsh_az

    def test_series_disambiguated_by_scheduled_time(self):
        # Same matchup on consecutive days; ticker time (26JUN05 21:40 ET ->
        # 2026-06-06T01:40Z) must select the Jun-5 game, not the Jun-4 one.
        market = _mlb_game_market("Washington", "Arizona", "Arizona",
                                  "KXMLBGAME-26JUN052140WSHAZ-AZ")
        jun4 = _h2h_event("Washington Nationals", "Arizona Diamondbacks",
                          2.0, 1.85, "2026-06-05T01:40:00Z")
        jun5 = _h2h_event("Washington Nationals", "Arizona Diamondbacks",
                          1.95, 1.9, "2026-06-06T01:40:00Z")
        assert find_market_event(market, [jun4, jun5]) is jun5

    def test_ambiguous_without_time_refuses(self):
        # Spread/total tickers carry no HHMM; two same-day same-matchup events
        # can't be disambiguated -> refuse (return None) rather than guess.
        market = {
            "ticker": "KXNHLSPREAD-26JUN09CARVGK-VGK2",
            "rules_primary": ("If Vegas wins by over 2.5 goals in the Carolina "
                              "at Vegas professional hockey game originally "
                              "scheduled for Jun 9, 2026, then the market "
                              "resolves to Yes."),
        }
        a = _h2h_event("Carolina Hurricanes", "Vegas Golden Knights",
                       2.1, 1.7, "2026-06-09T23:00:00Z")
        b = _h2h_event("Carolina Hurricanes", "Vegas Golden Knights",
                       2.0, 1.8, "2026-06-09T20:00:00Z")
        assert find_market_event(market, [a, b]) is None

    def test_series_single_event_wrong_date_refuses(self):
        # The 2nd contamination variant: a no-time (NBA-style) ticker with a
        # single same-matchup event in the feed on a DIFFERENT date. Matching
        # both teams is not enough — a Game-4 market must not price off the
        # only Game-1 event (home/away flips, favorite inverts).
        game4 = {
            "ticker": "KXNBAGAME-26JUN10SASNYK-SAS",
            "yes_sub_title": "San Antonio",
            "rules_primary": ("If San Antonio wins the Game 4: San Antonio at "
                              "New York professional basketball game originally "
                              "scheduled for Jun 10, 2026, then the market "
                              "resolves to Yes."),
        }
        # Only Game 1 (Jun 3, 20:30 ET -> 2026-06-04T00:30Z) is in the feed.
        game1 = _h2h_event("New York Knicks", "San Antonio Spurs",
                           2.4, 1.6, "2026-06-04T00:30:00Z")
        assert find_market_event(game4, [game1]) is None

    def test_no_time_ticker_matches_same_date(self):
        # The legitimate counterpart: a no-time ticker DOES match when the
        # single candidate falls on the ticker's ET date.
        game1 = {
            "ticker": "KXNBAGAME-26JUN03NYKSAS-NYK",
            "yes_sub_title": "New York",
            "rules_primary": ("If New York wins the Game 1: New York at San "
                              "Antonio professional basketball game originally "
                              "scheduled for Jun 3, 2026, then the market "
                              "resolves to Yes."),
        }
        ev = _h2h_event("New York Knicks", "San Antonio Spurs",
                        2.4, 1.6, "2026-06-04T00:30:00Z")  # Jun 3 20:30 ET
        assert find_market_event(game1, [ev]) is ev


class TestDetectEdgeGameContamination:
    """End-to-end regression: the scenario that produced the bogus +15% /
    +34.7% MLB edges must now yield no edge."""

    def test_wrong_opponent_game_yields_no_edge(self):
        market = _mlb_game_market("Washington", "Arizona", "Arizona",
                                  "KXMLBGAME-26JUN052140WSHAZ-AZ")
        # Feed only has Arizona-vs-Dodgers (Arizona a heavy dog) — exactly the
        # data that fabricated a huge NO-Arizona edge before the fix.
        feed = [_h2h_event("Los Angeles Dodgers", "Arizona Diamondbacks",
                           1.6, 2.5, "2026-06-05T01:41:00Z")]
        assert detect_edge_game(market, feed) is None

    def test_correct_game_still_produces_opportunity(self):
        market = _mlb_game_market("Washington", "Arizona", "Arizona",
                                  "KXMLBGAME-26JUN052140WSHAZ-AZ",
                                  yes_ask="0.40", no_ask="0.62")
        # Arizona ~54% fair (home favorite vs Washington); yes_ask 0.40 -> real
        # positive YES edge against the CORRECT opponent.
        feed = [_h2h_event("Washington Nationals", "Arizona Diamondbacks",
                           2.0, 1.85, "2026-06-06T01:40:00Z")]
        opp = detect_edge_game(market, feed)
        assert opp is not None
        assert 0.45 < opp.fair_value < 0.65   # sane, not a fabricated extreme
        assert opp.edge > 0


class TestSameCityDisambiguation:
    """2026-06-05: Kalshi truncates sub-titles, so a Dodgers market reads
    "Los Angeles D". The old first-match-wins loop + the weak city-word
    fallback (kalshi_words[0] == "los") matched BOTH LA teams, so the market
    silently took whichever team the odds feed listed first (the away Angels) —
    inverting the favorite and fabricating a +27.9% phantom edge on the
    Dodgers-lose side. Matching now ranks by strength and refuses on a tie."""

    def test_strength_substring_outranks_city_word(self):
        # "Los Angeles D" is a prefix of "...Dodgers" (tier 3) but only shares
        # the city word with "...Angels" (tier 1).
        assert _team_match_strength("Los Angeles Dodgers", "Los Angeles D") == 3
        assert _team_match_strength("Los Angeles Angels", "Los Angeles D") == 1
        assert _team_match_strength("Los Angeles Angels", "Los Angeles A") == 3
        assert _team_match_strength("Los Angeles Dodgers", "Los Angeles A") == 1

    def test_match_outcome_picks_unique_best(self):
        outcomes = [
            {"name": "Los Angeles Angels"},   # listed first (away)
            {"name": "Los Angeles Dodgers"},
        ]
        idx, ambiguous = _match_team_outcome(outcomes, "Los Angeles D")
        assert (idx, ambiguous) == (1, False)   # Dodgers, not the first-listed
        idx, ambiguous = _match_team_outcome(outcomes, "Los Angeles A")
        assert (idx, ambiguous) == (0, False)

    def test_match_outcome_city_only_is_ambiguous(self):
        # A bare city reference matches both LA teams equally -> refuse.
        outcomes = [
            {"name": "Los Angeles Angels"},
            {"name": "Los Angeles Dodgers"},
        ]
        idx, ambiguous = _match_team_outcome(outcomes, "Los Angeles")
        assert idx is None and ambiguous is True

    def test_consensus_resolves_correct_la_team(self):
        # Angels @ Dodgers: away dog 2.64, home favorite 1.51.
        ev = _h2h_event("Los Angeles Angels", "Los Angeles Dodgers",
                        2.64, 1.51, "2026-06-06T02:11:00Z")
        fair_dodgers, _ = consensus_fair_value([ev], "Los Angeles D")
        fair_angels, _ = consensus_fair_value([ev], "Los Angeles A")
        assert fair_dodgers > 0.6          # the favorite, not the dog
        assert fair_angels < 0.4
        assert fair_dodgers + fair_angels == pytest.approx(1.0, abs=0.001)

    def test_detect_edge_no_phantom_on_truncated_favorite(self):
        # Dodgers-win market (YES priced 0.65) against the real same-city game.
        # Before the fix this produced a bogus +27.9% NO ("Dodgers lose") edge.
        market = _mlb_game_market(
            "Los Angeles Angels", "Los Angeles Dodgers", "Los Angeles D",
            "KXMLBGAME-26JUN052210LAALAD-LAD", yes_ask="0.65", no_ask="0.36")
        feed = [_h2h_event("Los Angeles Angels", "Los Angeles Dodgers",
                           2.64, 1.51, "2026-06-06T02:11:00Z")]
        opp = detect_edge_game(market, feed)
        assert opp is not None
        # Fair must reflect the Dodgers' ~0.64 win prob, so neither side shows a
        # large edge against an efficiently-priced market.
        assert abs(opp.edge) < 0.05


class TestConsensusBeltAndSuspenders:
    """Fix B: consensus_* must refuse to pool one subject across >1 event,
    even if a caller forgets to pre-scope via find_market_event."""

    def test_fair_value_refuses_multi_event(self):
        feed = [
            _h2h_event("Los Angeles Dodgers", "Arizona Diamondbacks",
                       1.6, 2.5, "2026-06-05T01:41:00Z"),
            _h2h_event("Washington Nationals", "Arizona Diamondbacks",
                       2.0, 1.85, "2026-06-06T01:40:00Z"),
        ]
        # "Arizona" matches both events -> refuse.
        assert consensus_fair_value(feed, "Arizona") is None

    def test_fair_value_single_event_ok(self):
        feed = [_h2h_event("Washington Nationals", "Arizona Diamondbacks",
                           2.0, 1.85, "2026-06-06T01:40:00Z")]
        result = consensus_fair_value(feed, "Arizona")
        assert result is not None
        fair, details = result
        assert details["n_books"] == 2
        assert 0.4 < fair < 0.7

    def test_totals_refuses_multi_event(self):
        # consensus_total_prob keys only on "Over" (no team match), so two
        # events would silently blend without the guard.
        feed = [
            _totals_event("A", "B", 8.5, 1.9, "2026-06-05T01:41:00Z"),
            _totals_event("C", "D", 9.5, 1.9, "2026-06-06T01:40:00Z"),
        ]
        assert consensus_total_prob(feed, 9.0, ticker="KXMLBTOTAL-x") is None


class TestThreeWayDevig:
    """Soccer h2h is 3-way (home/draw/away). consensus_fair_value must treat a
    Kalshi 'team to win?' binary as the team's devigged WIN share — draw and
    opponent-win both belong to the NO side. Previously 3-outcome markets were
    skipped entirely (len != 2), so soccer produced no edges at all."""

    def _soccer_event(self, home, away, home_p, draw_p, away_p,
                      commence="2026-08-16T14:00:00Z"):
        return {
            "home_team": home,
            "away_team": away,
            "commence_time": commence,
            "bookmakers": [{
                "key": "pinnacle",
                "markets": [{
                    "key": "h2h",
                    "outcomes": [
                        {"name": home, "price": home_p},
                        {"name": away, "price": away_p},
                        {"name": "Draw", "price": draw_p},
                    ],
                }],
            }],
        }

    def test_three_way_uses_win_share(self):
        # implied: Chelsea 1/2.5=.4000, Arsenal 1/3.0=.3333, Draw 1/3.2=.3125
        # total .8458... wait -> sum=1.0458; Arsenal share = .3333/1.0458=.3187
        ev = self._soccer_event("Chelsea", "Arsenal", 2.5, 3.2, 3.0)
        result = consensus_fair_value([ev], "Arsenal")
        assert result is not None
        fair, details = result
        assert fair == pytest.approx(0.3187, abs=0.002)
        assert details["n_books"] == 1
        # Draw must not be mistaken for the team.
        assert 0.0 < fair < 0.5

    def test_three_way_draw_not_matched_as_team(self):
        # A team that doesn't appear returns None, not the Draw outcome.
        ev = self._soccer_event("Chelsea", "Arsenal", 2.5, 3.2, 3.0)
        assert consensus_fair_value([ev], "Liverpool") is None


class TestSpreadTotalDevig:
    """Spread/total models must de-vig the book's two-way line before inferring
    the mean, exactly as consensus_fair_value does for moneyline.

    Bug (2026-06-29): consensus_spread_prob / consensus_total_prob used the RAW
    implied cover/over probability. A two-way spread sums to ~1.05-1.08 implied,
    so the raw figure ran ~half the vig high, inflating the inferred mean — and
    thus P(cover)/P(over) — for BOTH sides of every game. On soccer spreads this
    made the model price both teams to over-cover and only ever bet YES.
    """

    FUTURE = "2099-08-16T14:00:00Z"  # pre-game (avoid the live-staleness gate)

    def test_spread_symmetric_vig_infers_mean_at_the_line(self):
        # Favorite -1.5 and underdog +1.5 BOTH priced 1.90 (each raw implied
        # 0.5263, sum 1.0526). De-vigged, the favorite's cover prob is exactly
        # 0.5, so the inferred mean margin must equal the line (1.5) — no vig
        # leak. With the raw 0.5263 it would land above 1.5.
        ev = _spread_event("Brazil", "Japan", -1.5, 1.90, 1.90, self.FUTURE)
        result = consensus_spread_prob([ev], "Brazil", 2.5,
                                       ticker="KXWCSPREAD-26JUL01BRAJPN-BRA3")
        assert result is not None
        _, d = result
        assert d["inferred_mean_margin"] == pytest.approx(1.5, abs=0.02)
        # raw implied is recorded distinctly and is the vigged (higher) figure
        assert d["books"][0]["raw_implied"] == pytest.approx(0.5263, abs=0.001)
        assert d["books"][0]["implied"] == pytest.approx(0.5, abs=0.001)

    def test_spread_devig_lowers_cover_prob_vs_raw(self):
        # Asymmetric vigged line; the de-vigged fair must be below what the raw
        # implied would have produced (the always-YES inflation).
        ev = _spread_event("Brazil", "Japan", -1.5, 1.50, 2.50, self.FUTURE)
        strike = 1.5
        fair_devig, d = consensus_spread_prob(
            [ev], "Brazil", strike, ticker="KXWCSPREAD-26JUL01BRAJPN-BRA2")
        raw_implied = d["books"][0]["raw_implied"]
        stdev = d["margin_stdev"]
        # reproduce the OLD (buggy) computation from the raw implied
        from scipy.stats import norm
        raw_mean = -(-1.5) - stdev * norm.ppf(1 - raw_implied)
        raw_fair = 1 - norm.cdf(strike, loc=raw_mean, scale=stdev)
        assert fair_devig < raw_fair          # de-vig reduced the cover prob
        assert d["inferred_mean_margin"] < raw_mean

    def test_total_symmetric_vig_infers_mean_at_the_line(self):
        # Over/Under both 1.90 -> de-vigged over prob 0.5 -> inferred mean total
        # equals the line. _totals_event already prices both sides equal.
        ev = _totals_event("A", "B", 2.5, 1.90, self.FUTURE)
        result = consensus_total_prob([ev], 3.5, ticker="KXWCTOTAL-26JUL01ABX-T35")
        assert result is not None
        _, d = result
        assert d["inferred_mean_total"] == pytest.approx(2.5, abs=0.02)
        assert d["books"][0]["raw_implied"] == pytest.approx(0.5263, abs=0.001)
        assert d["books"][0]["implied"] == pytest.approx(0.5, abs=0.001)

    def test_two_way_share_unchanged(self):
        # Regression: the proportional devig must match the old 2-way result.
        # implied: AZ 1/1.85=.5405, WSH 1/2.0=.5000; total 1.0405; AZ=.5195
        ev = _h2h_event("Washington Nationals", "Arizona Diamondbacks",
                        2.0, 1.85, "2026-06-06T01:40:00Z")
        fair, _ = consensus_fair_value([ev], "Arizona")
        assert fair == pytest.approx(0.5195, abs=0.002)


class TestWorldCupMappings:
    """World Cup (KXWC*) wiring — added 2026-06-20 to restore summer coverage.

    World Cup is soccer (3-way), so it reuses the existing soccer edge logic;
    these assert only the prefix/category wiring that makes the scanner pick
    the markets up and route them through game/spread/total edge detection.
    """

    def test_game_categorized_as_game(self):
        assert CATEGORY_MAP["KXWCGAME"] == "game"

    def test_spread_total_categories(self):
        assert CATEGORY_MAP["KXWCSPREAD"] == "spread"
        assert CATEGORY_MAP["KXWCTOTAL"] == "total"

    def test_odds_sport_key(self):
        assert KALSHI_TO_ODDS_SPORT["KXWCGAME"] == "soccer_fifa_world_cup"
        assert KALSHI_TO_ODDS_SPORT["KXWCSPREAD"] == "soccer_fifa_world_cup"
        assert KALSHI_TO_ODDS_SPORT["KXWCTOTAL"] == "soccer_fifa_world_cup"

    def test_stdev_resolves_to_soccer(self):
        # KXWC -> soccer in _PREFIX_TO_SPORT, so margin/total stdevs match soccer.
        assert _get_margin_stdev("KXWCGAME-26JUN27CODUZB-COD") == SPORT_MARGIN_STDEV["soccer"]
        assert _get_total_stdev("KXWCTOTAL-26JUN27CODUZB-5") == SPORT_TOTAL_STDEV["soccer"]


class TestMlbSpreadTotalMappings:
    """KXMLBSPREAD / KXMLBTOTAL wiring — added 2026-07-20.

    The series launched on Kalshi after MLB was first wired (March 2026), so
    MLB scanned moneyline-only all season while every other major sport had
    spread/total coverage. The R2-calibrated baseball stdevs were already in
    place; these assert the prefix/category/odds-key wiring that routes the
    markets through the existing (generic) spread/total edge detection.
    Live market shapes verified 2026-07-20: bracket-style, line in
    `floor_strike` (e.g. KXMLBSPREAD-26JUL202140CINSEA-SEA9 = "Seattle wins
    by over 8.5 runs", KXMLBTOTAL-26JUL211840MINCLE-9 = "Over 8.5 runs").
    """

    def test_mlb_filter_includes_spread_and_total(self):
        from edge_detector import FILTER_SHORTCUTS
        assert "KXMLBSPREAD" in FILTER_SHORTCUTS["mlb"]
        assert "KXMLBTOTAL" in FILTER_SHORTCUTS["mlb"]
        assert "KXMLBGAME" in FILTER_SHORTCUTS["mlb"]  # unchanged

    def test_spread_total_categories(self):
        assert CATEGORY_MAP["KXMLBSPREAD"] == "spread"
        assert CATEGORY_MAP["KXMLBTOTAL"] == "total"

    def test_odds_sport_key(self):
        assert KALSHI_TO_ODDS_SPORT["KXMLBSPREAD"] == "baseball_mlb"
        assert KALSHI_TO_ODDS_SPORT["KXMLBTOTAL"] == "baseball_mlb"

    def test_stdev_resolves_to_baseball(self):
        # KXMLB -> baseball_mlb in _PREFIX_TO_SPORT (prefix match covers the
        # new series), so the R2-calibrated run stdevs price these markets.
        assert _get_margin_stdev("KXMLBSPREAD-26JUL202140CINSEA-SEA9") == \
            SPORT_MARGIN_STDEV["baseball_mlb"]
        assert _get_total_stdev("KXMLBTOTAL-26JUL211840MINCLE-9") == \
            SPORT_TOTAL_STDEV["baseball_mlb"]

    def test_ticker_display_handles_new_series(self):
        from ticker_display import sport_from_ticker, bet_type_from_ticker
        assert sport_from_ticker("KXMLBSPREAD-26JUL202140CINSEA-SEA9") == "MLB"
        assert bet_type_from_ticker("KXMLBSPREAD-26JUL202140CINSEA-SEA9") == "Spread"
        assert bet_type_from_ticker("KXMLBTOTAL-26JUL211840MINCLE-9") == "Total"


class TestNbaConsensusBooks:
    """R29: Enforce stricter consensus book limits for NBA confidence."""

    def test_nba_low_books_forces_low_confidence(self):
        # NBA ticker with 5 books on 2026-04-21 (date must match commence time of event)
        market = _mlb_game_market("Los Angeles Lakers", "Boston Celtics", "Los Angeles Lakers", "KXNBAGAME-26APR21LALBOS-LAL", yes_ask="0.40", no_ask="0.62")
        feed = [_h2h_event("Los Angeles Lakers", "Boston Celtics", 2.0, 1.85, "2026-04-22T01:40:00Z", 
                           books=("pinnacle", "draftkings", "fanduel", "betmgm", "pointsbet"))]
        
        # Detect edge: NBA needs 8 books, so 5 books forces low confidence
        opp = detect_edge_game(market, feed)
        assert opp is not None
        assert opp.confidence == "low"

    def test_mlb_low_books_retains_medium_confidence(self):
        # MLB ticker with 5 books on 2026-04-21
        market = _mlb_game_market("New York Yankees", "Kansas City Royals", "New York Yankees", "KXMLBGAME-26APR21NYYKAC-NYY", yes_ask="0.40", no_ask="0.62")
        feed = [_h2h_event("New York Yankees", "Kansas City Royals", 2.0, 1.85, "2026-04-22T01:40:00Z", 
                           books=("pinnacle", "draftkings", "fanduel", "betmgm", "pointsbet"))]
        
        # MLB does not have NBA consensus books constraint, so 5 books gets medium confidence
        opp = detect_edge_game(market, feed)
        assert opp is not None
        assert opp.confidence == "medium"


class TestDynamicStdevLoading:
    """C8: dynamic loading of standard deviations from cached JSON file."""

    @pytest.fixture(autouse=True)
    def _reset_stdev_cache(self):
        """C8 overrides live in module-level globals that persist across tests.
        Reset them before AND after each test here so a populated override can't
        leak into a sibling test that expects the hardcoded defaults."""
        import edge_detector
        def _clear():
            edge_detector._last_loaded_stdev_time = 0.0
            edge_detector._cached_calibrated_margin_stdev = {}
            edge_detector._cached_calibrated_total_stdev = {}
        _clear()
        yield
        _clear()

    @patch("paths.DATA_DIR")
    def test_loads_overrides_when_present_and_fresh(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        
        # Write dummy calibration overrides
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        calibration_file = cache_dir / "calibration_stdevs.json"
        
        calibration_data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "margin_stdev": {
                "basketball_nba": 15.5,
                "baseball_mlb": 5.0
            },
            "total_stdev": {
                "basketball_nba": 25.0
            }
        }
        with open(calibration_file, "w", encoding="utf-8") as f:
            json.dump(calibration_data, f)
            
        with patch.dict(os.environ, {"TEST_CALIBRATION_STDEVS": "1"}):
            from app.config import reset_config
            reset_config()
            try:
                with patch("paths.DATA_DIR", tmp_path):
                    import edge_detector
                    edge_detector._last_loaded_stdev_time = 0.0
                    
                    # Check that lookups fetch the overrides
                    assert _get_margin_stdev("KXNBAGAME-...") == 15.5
                    assert _get_margin_stdev("KXMLBGAME-...") == 5.0
                    assert _get_total_stdev("KXNBATOTAL-...") == 25.0
                    
                    # Non-overridden sports fall back to baseline constants
                    assert _get_margin_stdev("KXNHLGAME-...") == SPORT_MARGIN_STDEV["icehockey_nhl"]
            finally:
                reset_config()

    @patch("paths.DATA_DIR")
    def test_falls_back_when_stale(self, mock_data_dir, tmp_path):
        mock_data_dir.return_value = tmp_path
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        calibration_file = cache_dir / "calibration_stdevs.json"
        
        calibration_data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "margin_stdev": {
                "basketball_nba": 15.5
            },
            "total_stdev": {}
        }
        with open(calibration_file, "w", encoding="utf-8") as f:
            json.dump(calibration_data, f)
            
        # Backdate the file by 31 days (default TTL is 30)
        mtime = time.time() - 31 * 86400
        os.utime(calibration_file, (mtime, mtime))
        
        with patch.dict(os.environ, {"TEST_CALIBRATION_STDEVS": "1"}):
            from app.config import reset_config
            reset_config()
            try:
                with patch("paths.DATA_DIR", tmp_path):
                    import edge_detector
                    edge_detector._last_loaded_stdev_time = 0.0
                    
                    # Should fall back to the default baseline constant (13.8)
                    assert _get_margin_stdev("KXNBAGAME-...") == 13.8
            finally:
                reset_config()

    @pytest.mark.parametrize("bad_value", [0, -5.0, "13.8", float("nan"), float("inf")])
    def test_falls_back_on_invalid_values(self, tmp_path, bad_value):
        """A single out-of-range / non-numeric stdev must reject the WHOLE map and
        fall back to defaults — never reach the CDF model (0 → every favorite ~100%,
        negative → scipy breaks, NaN → silently poisons every probability)."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        calibration_file = cache_dir / "calibration_stdevs.json"
        calibration_data = {
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "margin_stdev": {"basketball_nba": bad_value, "baseball_mlb": 5.0},
            "total_stdev": {},
        }
        with open(calibration_file, "w", encoding="utf-8") as f:
            json.dump(calibration_data, f)

        with patch.dict(os.environ, {"TEST_CALIBRATION_STDEVS": "1"}):
            from app.config import reset_config
            reset_config()
            try:
                with patch("paths.DATA_DIR", tmp_path):
                    import edge_detector
                    edge_detector._last_loaded_stdev_time = 0.0
                    # Whole map rejected: even the *valid* MLB entry is discarded.
                    assert _get_margin_stdev("KXNBAGAME-...") == SPORT_MARGIN_STDEV["basketball_nba"]
                    assert _get_margin_stdev("KXMLBGAME-...") == SPORT_MARGIN_STDEV["baseball_mlb"]
            finally:
                reset_config()

    def test_falls_back_on_unsupported_version(self, tmp_path):
        """A future/unknown schema version must fail safe to defaults, not silently
        retain whatever was cached before."""
        cache_dir = tmp_path / "cache"
        cache_dir.mkdir(parents=True, exist_ok=True)
        calibration_file = cache_dir / "calibration_stdevs.json"
        calibration_data = {
            "version": 2,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "margin_stdev": {"basketball_nba": 15.5},
            "total_stdev": {},
        }
        with open(calibration_file, "w", encoding="utf-8") as f:
            json.dump(calibration_data, f)

        with patch.dict(os.environ, {"TEST_CALIBRATION_STDEVS": "1"}):
            from app.config import reset_config
            reset_config()
            try:
                with patch("paths.DATA_DIR", tmp_path):
                    import edge_detector
                    edge_detector._last_loaded_stdev_time = 0.0
                    assert _get_margin_stdev("KXNBAGAME-...") == SPORT_MARGIN_STDEV["basketball_nba"]
            finally:
                reset_config()


class TestCalibrationStdevComputation:
    """C8-followup: significance-gated, sample-floored per-sport stdev calibration."""

    @staticmethod
    def _recs(n, fair_value, wins, category="spread", ticker="KXNBASPREAD-X", has_fv=True):
        return [
            {
                "ticker": ticker,
                "category": category,
                "fair_value": fair_value,
                "settlement_won": i < wins,
                "_has_fair_value": has_fv,
            }
            for i in range(n)
        ]

    def test_skips_below_min_samples(self):
        import model_calibration as mc
        # Overconfident (pred .65 vs real ~.42) but only 19 bets (< the 20 floor) — must not move.
        settled = self._recs(19, 0.65, 8)
        assert mc._calibrate_one_stdev(settled, "basketball_nba", 13.8, "spread") == 13.8

    def test_holds_when_gap_insignificant(self):
        import model_calibration as mc
        # 40 bets, pred .52 vs real .50 — a 2pp gap is within sampling noise.
        settled = self._recs(40, 0.52, 20)
        assert mc._calibrate_one_stdev(settled, "basketball_nba", 13.8, "spread") == 13.8

    def test_widens_on_significant_overconfidence(self):
        import model_calibration as mc
        # 60 bets, pred .55 vs real .40 — a 15pp gap clears the 1.96-SE gate.
        settled = self._recs(60, 0.55, 24)
        new = mc._calibrate_one_stdev(settled, "basketball_nba", 13.8, "spread")
        assert new > 13.8
        assert new <= round(13.8 * 1.25, 3)  # within the per-run ceiling

    def test_excludes_missing_fair_value(self):
        import model_calibration as mc
        # 60 overconfident bets but none carry a recorded fair_value -> all excluded.
        settled = self._recs(60, 0.55, 24, has_fv=False)
        assert mc._calibrate_one_stdev(settled, "basketball_nba", 13.8, "spread") == 13.8

    def test_clamps_extreme_multiplier(self):
        import model_calibration as mc
        # pred .95 vs real .30 would imply x1.65; the clamp caps it at x1.25.
        settled = self._recs(60, 0.95, 18)
        new = mc._calibrate_one_stdev(settled, "basketball_nba", 13.8, "spread")
        assert new == round(13.8 * 1.25, 3)


class TestLiveInPlayOddsPhase2:
    """L1 Phase 2: targeted live fetch and stale bookmaker exclusion."""

    @patch("edge_detector.fetch_event_odds_api")
    def test_refresh_event_if_live_updates_event_when_game_started(self, mock_fetch_event):
        from edge_detector import _refresh_event_if_live
        from datetime import datetime, timedelta, timezone
        
        # Scenario 1: Game not started yet (future commence time)
        commence_future = (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        market = {"ticker": "KXNBAGAME-26APR21LALBOS-LAL"}
        matched_event = {
            "id": "event_123",
            "sport_key": "basketball_nba",
            "commence_time": commence_future,
            "bookmakers": [{"key": "draftkings", "markets": []}]
        }
        
        result = _refresh_event_if_live(matched_event, market)
        assert result is matched_event
        mock_fetch_event.assert_not_called()
        
        # Scenario 2: Game started (commence time in the past)
        commence_past = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat().replace("+00:00", "Z")
        matched_event_past = {
            "id": "event_123",
            "sport_key": "basketball_nba",
            "commence_time": commence_past,
            "bookmakers": [{"key": "draftkings", "markets": []}]
        }
        
        refreshed_event = {
            "id": "event_123",
            "sport_key": "basketball_nba",
            "commence_time": commence_past,
            "bookmakers": [{"key": "draftkings", "markets": [{"key": "h2h", "outcomes": []}]}]
        }
        mock_fetch_event.return_value = refreshed_event
        
        result = _refresh_event_if_live(matched_event_past, market)
        assert result is refreshed_event
        mock_fetch_event.assert_called_once_with("basketball_nba", "event_123")

    def test_is_bookmaker_stale_excludes_stale_bookmaker_in_consensus(self):
        from edge_detector import _is_bookmaker_stale, consensus_fair_value, _parse_iso_utc
        from datetime import datetime, timedelta, timezone
        
        # Game in progress (started 10 mins ago)
        commence_time = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        
        # Stale bookmaker last updated 30 minutes ago (1800s ago > 1200s max)
        stale_lu = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        # Fresh bookmaker last updated 1 minute ago
        fresh_lu = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        
        event = {
            "commence_time": commence_time,
            "bookmakers": [
                {
                    "key": "pinnacle",
                    "last_update": fresh_lu,
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Lakers", "price": 1.5},
                            {"name": "Celtics", "price": 2.5}
                        ]
                    }]
                },
                {
                    "key": "draftkings",
                    "last_update": stale_lu,
                    "markets": [{
                        "key": "h2h",
                        "outcomes": [
                            {"name": "Lakers", "price": 2.0},
                            {"name": "Celtics", "price": 2.0}
                        ]
                    }]
                }
            ]
        }
        
        # Verify freshness check on bookmakers
        assert _is_bookmaker_stale(event["bookmakers"][0], event, 1200) is False
        assert _is_bookmaker_stale(event["bookmakers"][1], event, 1200) is True

        # Add two more fresh books so the live consensus survives the min-books
        # floor (default 3); the stale DraftKings line must still be excluded.
        for key in ("fanduel", "betmgm"):
            event["bookmakers"].append({
                "key": key,
                "last_update": fresh_lu,
                "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Lakers", "price": 1.5},
                    {"name": "Celtics", "price": 2.5},
                ]}],
            })

        result = consensus_fair_value([event], "Lakers")
        assert result is not None
        fair_prob, details = result
        assert fair_prob == pytest.approx(0.625, abs=0.001)
        assert "pinnacle" in details["books"]
        assert "draftkings" not in details["books"]  # stale -> excluded

        # If the event was pre-game, last_update is not checked for staleness
        pregame_commence = (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")
        event_pregame = dict(event, commence_time=pregame_commence)

        assert _is_bookmaker_stale(event_pregame["bookmakers"][0], event_pregame, 1200) is False
        assert _is_bookmaker_stale(event_pregame["bookmakers"][1], event_pregame, 1200) is False

        # Pre-game: even the otherwise-stale DraftKings line is included
        result_pregame = consensus_fair_value([event_pregame], "Lakers")
        assert result_pregame is not None
        _, details_pregame = result_pregame
        assert "pinnacle" in details_pregame["books"]
        assert "draftkings" in details_pregame["books"]

    def test_live_consensus_thinned_below_floor_returns_none(self):
        """CRITICAL #2: when the stale filter strips a live market below the
        min-books floor, refuse rather than price off 1-2 surviving quotes."""
        from edge_detector import consensus_fair_value
        from datetime import datetime, timedelta, timezone

        commence = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        fresh = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        stale = (datetime.now(timezone.utc) - timedelta(minutes=30)).isoformat().replace("+00:00", "Z")
        event = {
            "commence_time": commence,
            "bookmakers": [
                {"key": "pinnacle", "last_update": fresh, "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Lakers", "price": 1.5}, {"name": "Celtics", "price": 2.5}]}]},
                {"key": "draftkings", "last_update": stale, "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Lakers", "price": 2.0}, {"name": "Celtics", "price": 2.0}]}]},
            ],
        }
        # 1 fresh book survives (< floor 3) AND a book was excluded -> None.
        assert consensus_fair_value([event], "Lakers") is None

    def test_live_consensus_all_fresh_not_floored(self):
        """The floor only fires when staleness actually thinned the set. A live
        2-book market with both books fresh is no thinner than pre-game, so it
        still produces a consensus."""
        from edge_detector import consensus_fair_value
        from datetime import datetime, timedelta, timezone

        commence = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat().replace("+00:00", "Z")
        fresh = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat().replace("+00:00", "Z")
        event = {
            "commence_time": commence,
            "bookmakers": [
                {"key": "pinnacle", "last_update": fresh, "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Lakers", "price": 1.5}, {"name": "Celtics", "price": 2.5}]}]},
                {"key": "fanduel", "last_update": fresh, "markets": [{"key": "h2h", "outcomes": [
                    {"name": "Lakers", "price": 1.5}, {"name": "Celtics", "price": 2.5}]}]},
            ],
        }
        result = consensus_fair_value([event], "Lakers")
        assert result is not None
        assert result[1]["n_books"] == 2

    def test_missing_last_update_excluded_on_live_game(self):
        """CRITICAL #1: a book with no/unparseable last_update on a live game
        fails closed (excluded); pre-game it is untouched."""
        from edge_detector import _is_bookmaker_stale
        from datetime import datetime, timedelta, timezone

        live = {"commence_time": (datetime.now(timezone.utc) - timedelta(minutes=5)).isoformat().replace("+00:00", "Z")}
        pregame = {"commence_time": (datetime.now(timezone.utc) + timedelta(hours=2)).isoformat().replace("+00:00", "Z")}
        no_lu = {"key": "pinnacle", "markets": []}
        bad_lu = {"key": "pinnacle", "last_update": "not-a-timestamp", "markets": []}

        assert _is_bookmaker_stale(no_lu, live, 1200) is True
        assert _is_bookmaker_stale(bad_lu, live, 1200) is True
        assert _is_bookmaker_stale(no_lu, pregame, 1200) is False



class TestTennisMappings:
    """Wimbledon tennis (KXATPMATCH / KXWTAMATCH) wiring.

    Tennis is h2h match-winner only (no spread/total). ATP and WTA singles
    route to their respective Odds API keys. The rules_primary strings below are
    taken verbatim from live Kalshi markets (2026-06-29), so they exercise the
    real extraction + matching path rather than a fabricated pattern.
    """

    # Real rules_primary text from live KXATPMATCH / KXWTAMATCH markets.
    _ATP_RULES = (
        "If Stefanos Tsitsipas wins the Tsitsipas vs Djokovic professional "
        "tennis match in the 2026 Wimbledon Men Singles Round Of 64 after a "
        "ball has been played, then the market resolves to Yes."
    )
    _WTA_RULES = (
        "If Solana Sierra wins the Sierra vs Gauff professional tennis match "
        "in the 2026 Wimbledon Women Singles Round Of 64 after a ball has been "
        "played, then the market resolves to Yes."
    )

    def test_atp_match_categorized_as_game(self):
        assert CATEGORY_MAP["KXATPMATCH"] == "game"

    def test_wta_match_categorized_as_game(self):
        assert CATEGORY_MAP["KXWTAMATCH"] == "game"

    def test_atp_odds_sport_key(self):
        assert KALSHI_TO_ODDS_SPORT["KXATPMATCH"] == "tennis_atp_wimbledon"

    def test_wta_odds_sport_key(self):
        assert KALSHI_TO_ODDS_SPORT["KXWTAMATCH"] == "tennis_wta_wimbledon"

    def test_atp_extract_players_from_real_rules(self):
        # The existing "(?:vs|at) ... professional" pattern returns last names,
        # which substring-match the Odds API full names.
        market = {"ticker": "KXATPMATCH-26JUL01TSIDJO-TSI",
                  "rules_primary": self._ATP_RULES}
        assert extract_event_teams(market) == ("Tsitsipas", "Djokovic")

    def test_wta_extract_players_from_real_rules(self):
        market = {"ticker": "KXWTAMATCH-26JUL01SIEGAU-SIE",
                  "rules_primary": self._WTA_RULES}
        assert extract_event_teams(market) == ("Sierra", "Gauff")

    def test_find_event_tolerates_expiration_dated_ticker(self):
        # The ticker date (26JUL01) is the market's *expected expiration*, ~a day
        # AFTER the match commences (Jun 30 09:00 UTC). Exact ET-date equality
        # would miss it; the tennis branch accepts the single player-pair
        # candidate within a few days.
        market = {"ticker": "KXATPMATCH-26JUL01TSIDJO-TSI",
                  "yes_sub_title": "Stefanos Tsitsipas",
                  "rules_primary": self._ATP_RULES}
        ev = _h2h_event("Stefanos Tsitsipas", "Novak Djokovic",
                        4.5, 1.2, "2026-06-30T09:00:00Z")
        assert find_market_event(market, [ev]) is ev

    def test_find_event_refuses_far_off_date(self):
        # A candidate whose commence is far from the ticker date is a stale /
        # wrong-tournament listing — refuse rather than fabricate an edge.
        market = {"ticker": "KXATPMATCH-26JUL01TSIDJO-TSI",
                  "yes_sub_title": "Stefanos Tsitsipas",
                  "rules_primary": self._ATP_RULES}
        ev = _h2h_event("Stefanos Tsitsipas", "Novak Djokovic",
                        4.5, 1.2, "2026-06-20T09:00:00Z")
        assert find_market_event(market, [ev]) is None
