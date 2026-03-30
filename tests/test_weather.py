"""Tests for weather scoring adjustments in sports_weather.py."""

import pytest

from sports_weather import weather_scoring_adjustment


class TestWeatherScoringAdjustment:
    """Verify weather impact thresholds for MLB and NFL."""

    # ── MLB thresholds ───────────────────────────────────────────────────

    def test_mlb_high_wind(self):
        weather = {"wind_speed_mph": 25, "precip_pct": 0, "temperature_f": 70}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["adjustment"] <= -0.06
        assert result["severity"] in ("moderate", "severe")

    def test_mlb_moderate_wind(self):
        weather = {"wind_speed_mph": 15, "precip_pct": 0, "temperature_f": 70}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["adjustment"] <= -0.03

    def test_mlb_high_rain(self):
        weather = {"wind_speed_mph": 0, "precip_pct": 60, "temperature_f": 70}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["adjustment"] <= -0.05

    def test_mlb_cold(self):
        weather = {"wind_speed_mph": 0, "precip_pct": 0, "temperature_f": 40}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["adjustment"] <= -0.03

    def test_mlb_perfect_weather(self):
        weather = {"wind_speed_mph": 5, "precip_pct": 10, "temperature_f": 75}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["adjustment"] == 0
        assert result["severity"] == "none"

    def test_mlb_combined_bad_weather(self):
        weather = {"wind_speed_mph": 22, "precip_pct": 55, "temperature_f": 40}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["adjustment"] <= -0.10
        assert result["severity"] == "severe"

    # ── NFL thresholds ───────────────────────────────────────────────────

    def test_nfl_blizzard(self):
        weather = {"wind_speed_mph": 30, "precip_pct": 80, "temperature_f": 15}
        result = weather_scoring_adjustment(weather, "americanfootball_nfl")
        assert result["adjustment"] <= -0.15
        assert result["severity"] == "severe"

    def test_nfl_perfect_dome_like(self):
        weather = {"wind_speed_mph": 3, "precip_pct": 5, "temperature_f": 65}
        result = weather_scoring_adjustment(weather, "americanfootball_nfl")
        assert result["adjustment"] == 0
        assert result["severity"] == "none"

    # ── Severity mapping ─────────────────────────────────────────────────

    def test_severity_none(self):
        weather = {"wind_speed_mph": 0, "precip_pct": 0, "temperature_f": 70}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["severity"] == "none"

    def test_severity_mild(self):
        weather = {"wind_speed_mph": 13, "precip_pct": 0, "temperature_f": 70}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert result["severity"] == "mild"

    # ── Return structure ─────────────────────────────────────────────────

    def test_return_keys(self):
        weather = {"wind_speed_mph": 10, "precip_pct": 20, "temperature_f": 60}
        result = weather_scoring_adjustment(weather, "baseball_mlb")
        assert "adjustment" in result
        assert "reason" in result
        assert "severity" in result
        assert isinstance(result["adjustment"], (int, float))
        assert isinstance(result["reason"], str)
        assert result["severity"] in ("none", "mild", "moderate", "severe")
