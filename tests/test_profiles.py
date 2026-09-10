"""P1 — strategy profile overlays (`--profile <name>` / `.env.<name>`).

A profile is how one codebase runs two strategies against two Kalshi
subaccounts. It replaced a second checkout of this repo, whose real code delta
was ~74 lines and whose strategy delta was two env vars — and which had already
drifted into a live defect (a stale NCAAF ticker prefix that scanned zero
college football all season) while missing two fixes made on this side.

The behaviour under test that actually protects money is **fail-closed**: a
profile that cannot be resolved must stop the run, never silently fall back to
the base `.env`. The base `.env` is the live-money wallet (`DRY_RUN=false`,
subaccount 0); the longshot overlay is a dry-run evidence window on subaccount
1. A typo'd `--profile longshto` that fell through to the base config would run
one strategy's intent against the other strategy's bankroll, live.
"""

import os

import pytest

from app.config import (
    Config,
    apply_profile_overlay,
    get_config,
    reset_config,
)


@pytest.fixture(autouse=True)
def _clean_config():
    """Every test here mutates os.environ; never leak a memoized Config."""
    reset_config()
    yield
    os.environ.pop("EDGE_RADAR_PROFILE", None)
    reset_config()


class TestUnprofiledDefault:
    def test_no_env_var_is_main(self, monkeypatch):
        monkeypatch.delenv("EDGE_RADAR_PROFILE", raising=False)
        assert apply_profile_overlay() == "main"

    def test_explicit_main_is_a_noop(self, monkeypatch):
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "main")
        monkeypatch.setenv("KALSHI_SUBACCOUNT", "0")
        assert apply_profile_overlay() == "main"
        assert os.environ["KALSHI_SUBACCOUNT"] == "0"

    def test_config_reports_main(self, monkeypatch):
        monkeypatch.delenv("EDGE_RADAR_PROFILE", raising=False)
        assert get_config().system.profile == "main"

    def test_subaccount_defaults_to_primary(self, monkeypatch):
        """An unprofiled run must be byte-identical to pre-P1 behaviour."""
        monkeypatch.delenv("KALSHI_SUBACCOUNT", raising=False)
        assert Config.from_env().kalshi.subaccount == 0


class TestFailsClosed:
    """The whole point. None of these may resolve to the base `.env`."""

    def test_missing_overlay_file_raises(self, monkeypatch, tmp_path):
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "nosuchprofile")
        with pytest.raises(FileNotFoundError, match="nosuchprofile"):
            apply_profile_overlay()

    def test_typo_does_not_silently_become_main(self, monkeypatch, tmp_path):
        """`--profile longshto` must stop, not bet the main bankroll."""
        (tmp_path / ".env.longshot").write_text("KALSHI_SUBACCOUNT=1\n")
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "longshto")
        monkeypatch.setenv("KALSHI_SUBACCOUNT", "0")
        with pytest.raises(FileNotFoundError):
            apply_profile_overlay()
        # and the environment is untouched — no half-applied overlay
        assert os.environ["KALSHI_SUBACCOUNT"] == "0"

    @pytest.mark.parametrize("bad", ["../.env", "a/b", "sub dir", "x;y", "*"])
    def test_path_shaped_names_are_rejected(self, monkeypatch, bad):
        monkeypatch.setenv("EDGE_RADAR_PROFILE", bad)
        with pytest.raises(ValueError, match="valid profile name"):
            apply_profile_overlay()


class TestOverlaySemantics:
    def test_overlay_wins_over_the_base_env(self, monkeypatch, tmp_path):
        (tmp_path / ".env.longshot").write_text(
            "KALSHI_SUBACCOUNT=1\nDRY_RUN=true\nMIN_MARKET_PRICE=0.08\n")
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "longshot")
        # base `.env` state: live money on the primary account
        monkeypatch.setenv("KALSHI_SUBACCOUNT", "0")
        monkeypatch.setenv("DRY_RUN", "false")
        monkeypatch.setenv("MIN_MARKET_PRICE", "0.10")

        assert apply_profile_overlay() == "longshot"

        cfg = Config.from_env()
        assert cfg.kalshi.subaccount == 1
        assert cfg.system.dry_run is True
        assert cfg.gates.min_market_price == 0.08

    def test_unlisted_keys_are_inherited(self, monkeypatch, tmp_path):
        """The reason the overlay beats a forked repo: everything the profile
        does NOT mention stays in lockstep — risk gates, fee model, freezes."""
        (tmp_path / ".env.longshot").write_text("KALSHI_SUBACCOUNT=1\n")
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "longshot")
        monkeypatch.setenv("MAX_OPEN_EXPOSURE_PCT", "0.50")
        monkeypatch.setenv("MAX_SEGMENT_EXPOSURE_PCT", "0.33")
        monkeypatch.setenv("MAX_BET_SIZE", "8")

        apply_profile_overlay()

        cfg = Config.from_env()
        assert cfg.kalshi.subaccount == 1
        assert cfg.risk.max_open_exposure_pct == 0.50
        assert cfg.risk.max_segment_exposure_pct == 0.33
        assert cfg.risk.max_bet_size == 8

    def test_profile_lands_on_config(self, monkeypatch, tmp_path):
        (tmp_path / ".env.longshot").write_text("KALSHI_SUBACCOUNT=1\n")
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "longshot")
        apply_profile_overlay()
        assert Config.from_env().system.profile == "longshot"

    def test_idempotent(self, monkeypatch, tmp_path):
        (tmp_path / ".env.longshot").write_text("KALSHI_SUBACCOUNT=1\n")
        monkeypatch.setenv("PROJECT_ROOT", str(tmp_path))
        monkeypatch.setenv("EDGE_RADAR_PROFILE", "longshot")
        assert apply_profile_overlay() == "longshot"
        assert apply_profile_overlay() == "longshot"
        assert os.environ["KALSHI_SUBACCOUNT"] == "1"


class TestSubaccountValidation:
    @pytest.mark.parametrize("n", [0, 1, 63])
    def test_valid_range(self, monkeypatch, n):
        monkeypatch.setenv("KALSHI_SUBACCOUNT", str(n))
        assert Config.from_env().kalshi.subaccount == n

    @pytest.mark.parametrize("n", [-1, 64, 999])
    def test_out_of_range_rejected(self, monkeypatch, n):
        monkeypatch.setenv("KALSHI_SUBACCOUNT", str(n))
        with pytest.raises(ValueError, match="KALSHI_SUBACCOUNT"):
            Config.from_env()


class TestScanDispatcherFlag:
    """`--profile` is consumed by scan.py, not forwarded to the scanners."""

    @staticmethod
    def _extract(args):
        import importlib.util
        from pathlib import Path

        root = Path(__file__).resolve().parent.parent
        spec = importlib.util.spec_from_file_location(
            "_scan_mod", root / "scripts" / "scan.py")
        mod = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(mod)
        return mod._extract_profile(args)

    def test_space_form(self):
        rest, profile = self._extract(["--filter", "mlb", "--profile", "longshot"])
        assert profile == "longshot"
        assert rest == ["--filter", "mlb"]

    def test_equals_form(self):
        rest, profile = self._extract(["--profile=longshot", "--save"])
        assert profile == "longshot"
        assert rest == ["--save"]

    def test_absent(self):
        rest, profile = self._extract(["--filter", "mlb", "--execute"])
        assert profile is None
        assert rest == ["--filter", "mlb", "--execute"]

    def test_does_not_swallow_the_next_flag(self):
        """`--profile --save` is a typo, not a profile named '--save'."""
        with pytest.raises(SystemExit):
            self._extract(["--profile", "--save"])


class TestTradeLogScoping:
    """The trade log is shared, so gates that read HISTORY must be scoped.

    Gate 1 (daily loss) and Gate 7 (series dedup) read it; Gates 5 and 6 read
    live venue positions, which Kalshi already scopes by subaccount. Unscoped,
    a bad day on `main` halts `longshot` and a matchup one profile bet blocks
    the other — across two genuinely separate wallets.
    """

    ROWS = [
        {"ticker": "A", "profile": "main", "net_pnl": -5},
        {"ticker": "B", "profile": "longshot", "net_pnl": -1},
        {"ticker": "C", "net_pnl": -9},  # pre-P1 row: no `profile` key
    ]

    def test_splits_by_profile(self):
        from trade_log import for_profile
        assert [r["ticker"] for r in for_profile(self.ROWS, "longshot")] == ["B"]

    def test_pre_p1_rows_belong_to_main(self):
        """Every row written before P1 came from the one book that existed."""
        from trade_log import for_profile
        assert [r["ticker"] for r in for_profile(self.ROWS, "main")] == ["A", "C"]

    def test_profiles_do_not_see_each_other(self):
        from trade_log import for_profile
        main = {r["ticker"] for r in for_profile(self.ROWS, "main")}
        longshot = {r["ticker"] for r in for_profile(self.ROWS, "longshot")}
        assert main & longshot == set()
        assert main | longshot == {"A", "B", "C"}

    def test_daily_pnl_is_scoped(self):
        """Gate 1 must not halt one profile for the other's losses."""
        from trade_log import for_profile, get_today_pnl
        import datetime as _dt

        today = _dt.datetime.now(_dt.timezone.utc).strftime("%Y-%m-%d")
        rows = [
            {"profile": "main", "net_pnl": -40, "closed_at": f"{today}T12:00:00Z"},
            {"profile": "longshot", "net_pnl": -1, "closed_at": f"{today}T12:00:00Z"},
        ]
        assert get_today_pnl(for_profile(rows, "longshot")) == -1
        assert get_today_pnl(for_profile(rows, "main")) == -40
        # unscoped is the bug: longshot would see -41 and trip a -$30 limit
        assert get_today_pnl(rows) == -41

    def test_defaults_to_the_active_profile(self, monkeypatch):
        from trade_log import for_profile
        monkeypatch.delenv("EDGE_RADAR_PROFILE", raising=False)
        reset_config()
        assert [r["ticker"] for r in for_profile(self.ROWS)] == ["A", "C"]
