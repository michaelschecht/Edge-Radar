"""Tests for app/config.py — the centralized config module.

Phase 1 of CONFIG_CENTRALIZATION: this module is pure addition. These tests
lock in the type-coercion contract and the `validate()` rules so Phase 2
script migrations can rely on them without re-checking each call site.
"""

import os
import pytest
from unittest.mock import patch

from app.config import (
    Config,
    KalshiCredentials,
    OddsApiCredentials,
    RiskLimits,
    GateThresholds,
    KellyConfig,
    PerSportOverrides,
    System,
    get_config,
    reset_config,
)


# ── Coercion contract ───────────────────────────────────────────────────────

class TestTypeCoercion:
    """Every field comes back as the declared dataclass type, not str."""

    @patch.dict(os.environ, {}, clear=True)
    def test_defaults_are_native_types(self):
        cfg = Config.from_env()
        # Floats
        assert isinstance(cfg.risk.unit_size, float)
        assert isinstance(cfg.risk.max_bet_size, float)
        assert isinstance(cfg.gates.min_edge_threshold, float)
        assert isinstance(cfg.gates.min_market_price, float)
        assert isinstance(cfg.kelly.kelly_fraction, float)
        # Ints
        assert isinstance(cfg.risk.max_open_positions, int)
        assert isinstance(cfg.risk.max_per_event, int)
        assert isinstance(cfg.gates.series_dedup_hours, int)
        # Bools
        assert isinstance(cfg.system.dry_run, bool)
        assert isinstance(cfg.gates.allow_prediction_bets, bool)
        # Strings
        assert isinstance(cfg.gates.min_confidence, str)
        assert isinstance(cfg.system.log_level, str)
        # Lists
        assert isinstance(cfg.odds.keys, list)

    @patch.dict(os.environ, {
        "MIN_EDGE_THRESHOLD": "0.07",
        "MAX_OPEN_POSITIONS": "25",
        "DRY_RUN": "false",
        "ODDS_API_KEYS": "k1,k2,k3",
    }, clear=True)
    def test_string_values_coerce_to_typed(self):
        cfg = Config.from_env()
        assert cfg.gates.min_edge_threshold == 0.07
        assert isinstance(cfg.gates.min_edge_threshold, float)
        assert cfg.risk.max_open_positions == 25
        assert isinstance(cfg.risk.max_open_positions, int)
        assert cfg.system.dry_run is False
        assert cfg.odds.keys == ["k1", "k2", "k3"]

    @patch.dict(os.environ, {"DRY_RUN": "TRUE"}, clear=True)
    def test_dry_run_case_insensitive(self):
        assert Config.from_env().system.dry_run is True

    @patch.dict(os.environ, {"DRY_RUN": "1"}, clear=True)
    def test_dry_run_accepts_numeric_truthy(self):
        assert Config.from_env().system.dry_run is True

    @patch.dict(os.environ, {"DRY_RUN": "no"}, clear=True)
    def test_dry_run_falsy_strings(self):
        assert Config.from_env().system.dry_run is False

    @patch.dict(os.environ, {"ODDS_API_KEYS": "  k1  ,  ,k2,"}, clear=True)
    def test_list_strips_and_skips_empties(self):
        assert Config.from_env().odds.keys == ["k1", "k2"]

    @patch.dict(os.environ, {"MIN_CONFIDENCE": "  HIGH  "}, clear=True)
    def test_min_confidence_normalized(self):
        assert Config.from_env().gates.min_confidence == "high"

    @patch.dict(os.environ, {"LOG_LEVEL": "  debug  "}, clear=True)
    def test_log_level_normalized(self):
        assert Config.from_env().system.log_level == "DEBUG"

    @patch.dict(os.environ, {"KALSHI_BASE_URL": "https://example.com/v2/"}, clear=True)
    def test_kalshi_base_url_strips_trailing_slash(self):
        assert Config.from_env().kalshi.base_url == "https://example.com/v2"

    @patch.dict(os.environ, {"MIN_EDGE_THRESHOLD": "not-a-number"}, clear=True)
    def test_invalid_float_raises(self):
        with pytest.raises(ValueError, match="MIN_EDGE_THRESHOLD"):
            Config.from_env()

    @patch.dict(os.environ, {"MAX_OPEN_POSITIONS": "ten"}, clear=True)
    def test_invalid_int_raises(self):
        with pytest.raises(ValueError, match="MAX_OPEN_POSITIONS"):
            Config.from_env()


# ── Default values match documented behavior ───────────────────────────────

class TestDocumentedDefaults:
    """Lock the defaults that risk-gate code depends on."""

    @patch.dict(os.environ, {}, clear=True)
    def test_risk_defaults(self):
        r = RiskLimits.from_env()
        assert r.unit_size == 1.00
        assert r.max_bet_size == 100.0
        assert r.max_daily_loss == 250.0
        assert r.max_open_positions == 10
        assert r.max_per_event == 2
        assert r.max_bet_ratio == 3.0

    @patch.dict(os.environ, {}, clear=True)
    def test_gate_defaults(self):
        g = GateThresholds.from_env()
        assert g.min_edge_threshold == 0.03
        assert g.min_market_price == 0.10
        assert g.min_composite_score == 6.0
        assert g.min_confidence == "medium"
        assert g.series_dedup_hours == 48
        assert g.resting_order_max_hours == 24
        assert g.allow_prediction_bets is False
        assert g.no_side_favorite_threshold == 0.25
        assert g.no_side_min_edge == 0.25

    @patch.dict(os.environ, {}, clear=True)
    def test_kelly_defaults(self):
        k = KellyConfig.from_env()
        assert k.kelly_fraction == 0.25
        assert k.kelly_edge_cap == 0.15
        assert k.kelly_edge_decay == 0.5
        assert k.no_side_kelly_price_floor == 0.35
        assert k.no_side_kelly_multiplier == 0.5

    @patch.dict(os.environ, {}, clear=True)
    def test_system_defaults(self):
        s = System.from_env()
        assert s.dry_run is True
        assert s.log_level == "INFO"
        assert s.project_root == ""

    @patch.dict(os.environ, {}, clear=True)
    def test_kalshi_defaults(self):
        k = KalshiCredentials.from_env()
        assert k.api_key == ""
        # Empty default preserves the kalshi_client.py "credentials not configured"
        # error path when KALSHI_PRIVATE_KEY_PATH is unset.
        assert k.private_key_path == ""
        assert k.private_key_inline == ""
        assert k.base_url == "https://api.elections.kalshi.com/trade-api/v2"


# ── Per-sport overrides ─────────────────────────────────────────────────────

class TestPerSportOverrides:
    @patch.dict(os.environ, {}, clear=True)
    def test_no_overrides_when_unset(self):
        assert PerSportOverrides.from_env().min_edge == {}

    @patch.dict(os.environ, {
        "MIN_EDGE_THRESHOLD_NBA": "0.12",
        "MIN_EDGE_THRESHOLD_NCAAB": "0.10",
    }, clear=True)
    def test_only_set_sports_appear(self):
        overrides = PerSportOverrides.from_env()
        assert overrides.min_edge == {"nba": 0.12, "ncaab": 0.10}

    @patch.dict(os.environ, {"MIN_EDGE_THRESHOLD_MLB": "garbage"}, clear=True)
    def test_invalid_value_skipped_silently(self):
        # Matches current kalshi_executor behavior: bad value is skipped, not raised.
        assert PerSportOverrides.from_env().min_edge == {}

    @patch.dict(os.environ, {"MIN_EDGE_THRESHOLD_NBA": "0.12"}, clear=True)
    def test_resolver_falls_back_to_global(self):
        cfg = Config.from_env()
        assert cfg.edge_threshold_for_sport("nba") == 0.12
        assert cfg.edge_threshold_for_sport("mlb") == cfg.gates.min_edge_threshold
        # Case-insensitive lookup
        assert cfg.edge_threshold_for_sport("NBA") == 0.12
        # Empty / unknown sport falls back to global
        assert cfg.edge_threshold_for_sport("") == cfg.gates.min_edge_threshold


# ── Validation ──────────────────────────────────────────────────────────────

class TestValidate:
    @patch.dict(os.environ, {"UNIT_SIZE": "150", "MAX_BET_SIZE": "50"}, clear=True)
    def test_max_bet_below_unit_raises(self):
        with pytest.raises(ValueError, match="MAX_BET_SIZE"):
            Config.from_env()

    @patch.dict(os.environ, {"UNIT_SIZE": "0"}, clear=True)
    def test_zero_unit_size_raises(self):
        with pytest.raises(ValueError, match="UNIT_SIZE"):
            Config.from_env()

    @patch.dict(os.environ, {"MAX_DAILY_LOSS": "-10"}, clear=True)
    def test_negative_daily_loss_raises(self):
        with pytest.raises(ValueError, match="MAX_DAILY_LOSS"):
            Config.from_env()

    @patch.dict(os.environ, {"MIN_CONFIDENCE": "extreme"}, clear=True)
    def test_invalid_confidence_raises(self):
        with pytest.raises(ValueError, match="MIN_CONFIDENCE"):
            Config.from_env()

    @patch.dict(os.environ, {"KELLY_FRACTION": "1.5"}, clear=True)
    def test_kelly_fraction_above_one_raises(self):
        with pytest.raises(ValueError, match="KELLY_FRACTION"):
            Config.from_env()

    @patch.dict(os.environ, {"KELLY_FRACTION": "-0.1"}, clear=True)
    def test_kelly_fraction_negative_raises(self):
        with pytest.raises(ValueError, match="KELLY_FRACTION"):
            Config.from_env()

    @patch.dict(os.environ, {"MIN_MARKET_PRICE": "1.5"}, clear=True)
    def test_min_market_price_above_one_raises(self):
        with pytest.raises(ValueError, match="MIN_MARKET_PRICE"):
            Config.from_env()

    @patch.dict(os.environ, {"LOG_LEVEL": "TRACE"}, clear=True)
    def test_invalid_log_level_raises(self):
        with pytest.raises(ValueError, match="LOG_LEVEL"):
            Config.from_env()

    @patch.dict(os.environ, {"MIN_MARKET_PRICE": "0"}, clear=True)
    def test_zero_min_market_price_allowed(self):
        # 0 disables the gate per .env.example — must not raise.
        Config.from_env()


# ── Memoization ─────────────────────────────────────────────────────────────

class TestMemoization:
    def setup_method(self):
        reset_config()

    def teardown_method(self):
        reset_config()

    @patch.dict(os.environ, {"MIN_EDGE_THRESHOLD": "0.05"}, clear=True)
    def test_get_config_caches(self):
        first = get_config()
        second = get_config()
        assert first is second  # same object, no re-read

    def test_reset_config_forces_reread(self):
        with patch.dict(os.environ, {"MIN_EDGE_THRESHOLD": "0.05"}, clear=True):
            first = get_config()
            assert first.gates.min_edge_threshold == 0.05
        reset_config()
        with patch.dict(os.environ, {"MIN_EDGE_THRESHOLD": "0.09"}, clear=True):
            second = get_config()
            assert second.gates.min_edge_threshold == 0.09
            assert second is not first

    def test_reset_config_handles_uninitialized(self):
        reset_config()  # already None, must not raise
        reset_config()
