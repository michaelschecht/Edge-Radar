"""Tests for edge detection math — normal CDF models and de-vigging."""

from unittest.mock import MagicMock, patch

import pytest
from scipy.stats import norm

from futures_edge import devig_nway


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


# ── Normal CDF spread model (math validation) ───────────────────────────────

class TestSpreadMath:
    """Validate the normal CDF model used for spread probability.

    The actual function (consensus_spread_prob) requires API data,
    so we test the underlying math directly.
    """

    def test_even_spread_gives_fifty_percent(self):
        # If book spread = 0 and implied = 50%, mean margin = 0
        # P(margin > 0) should be ~50%
        stdev = 12.0  # NBA
        mean_margin = 0.0
        prob = 1 - norm.cdf(0, loc=mean_margin, scale=stdev)
        assert abs(prob - 0.5) < 0.001

    def test_favorite_covers_large_spread(self):
        # Team favored by 10, but Kalshi strike is -3 (easier to cover)
        stdev = 12.0
        mean_margin = 10.0  # expected to win by 10
        strike = -3.0
        prob = 1 - norm.cdf(strike, loc=mean_margin, scale=stdev)
        assert prob > 0.85

    def test_underdog_covers_tough_spread(self):
        # Underdog (mean margin -5), strike is +7 (very hard to cover)
        stdev = 12.0
        mean_margin = -5.0
        strike = 7.0
        prob = 1 - norm.cdf(strike, loc=mean_margin, scale=stdev)
        assert prob < 0.20

    def test_mlb_lower_variance(self):
        # MLB stdev is 3.5 — same margin difference should produce more extreme probs
        stdev_mlb = 3.5
        stdev_nba = 12.0
        mean = 2.0
        strike = 0.0

        prob_mlb = 1 - norm.cdf(strike, loc=mean, scale=stdev_mlb)
        prob_nba = 1 - norm.cdf(strike, loc=mean, scale=stdev_nba)

        # MLB should be more confident (less variance)
        assert prob_mlb > prob_nba


class TestTotalMath:
    """Validate the normal CDF model for over/under totals."""

    def test_over_at_median_is_fifty(self):
        stdev = 18.0  # NBA
        expected_total = 220.0
        strike = 220.0
        prob_over = 1 - norm.cdf(strike, loc=expected_total, scale=stdev)
        assert abs(prob_over - 0.5) < 0.001

    def test_over_well_below_expected(self):
        # Strike well below expected total — high over probability
        stdev = 18.0
        expected_total = 230.0
        strike = 210.0
        prob_over = 1 - norm.cdf(strike, loc=expected_total, scale=stdev)
        assert prob_over > 0.85

    def test_over_well_above_expected(self):
        # Strike well above expected total — low over probability
        stdev = 18.0
        expected_total = 210.0
        strike = 240.0
        prob_over = 1 - norm.cdf(strike, loc=expected_total, scale=stdev)
        assert prob_over < 0.10


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
