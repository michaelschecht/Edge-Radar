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
        """Redirect the odds_api on-disk quota cache to a tmpdir so
        mark_exhausted() during these tests doesn't clobber real keys.
        """
        import odds_api
        monkeypatch.setattr(odds_api, "_QUOTA_CACHE_PATH", tmp_path / "quota.json")

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
