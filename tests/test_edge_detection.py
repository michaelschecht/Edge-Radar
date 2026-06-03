"""Tests for edge detection math — normal CDF models and de-vigging."""

from unittest.mock import MagicMock, patch

import pytest
from scipy.stats import norm

from edge_detector import (
    SPORT_MARGIN_STDEV,
    SPORT_TOTAL_STDEV,
    _adjust_confidence_with_stats,
    _get_margin_stdev,
    _get_total_stdev,
    consensus_fair_value,
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
        assert FUTURES_MAP["KXPGATOUR"][2] == "PGA Tour Winner"


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


# ── Opponent-validated event matching (fix A + B) ─────────────────────────────

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

    def test_two_way_share_unchanged(self):
        # Regression: the proportional devig must match the old 2-way result.
        # implied: AZ 1/1.85=.5405, WSH 1/2.0=.5000; total 1.0405; AZ=.5195
        ev = _h2h_event("Washington Nationals", "Arizona Diamondbacks",
                        2.0, 1.85, "2026-06-06T01:40:00Z")
        fair, _ = consensus_fair_value([ev], "Arizona")
        assert fair == pytest.approx(0.5195, abs=0.002)
