"""Guards on the C8 stdev-recalibration loop's configuration.

The loop went silently dead for its whole life and nothing caught it. Two
independent causes, both config rather than logic:

1. `model_calibration.CURRENT_*_STDEV` is a hand-copied duplicate of
   `edge_detector.SPORT_*_STDEV`. It is the *baseline* every calibration
   multiplies against, so if the two drift apart the loop calibrates away from
   a number the pricing model no longer uses.

2. `save_calibration_stdevs()` is handed a DAY-FILTERED settled list, and each
   (sport, category) needs `_MIN_CALIB_SAMPLES` rows before it will move. The
   weekly scheduler passed `--days 7`, a window in which only ~22 bets settle
   across *all* sports — so every sport was skipped and the hardcoded defaults
   were written straight back, every week, indefinitely.
"""

import re
from pathlib import Path

import pytest

import model_calibration as mc
from edge_detector import SPORT_MARGIN_STDEV, SPORT_TOTAL_STDEV

PROJECT_ROOT = Path(__file__).resolve().parent.parent


class TestBaselineDoesNotDriftFromPricing:
    """CURRENT_*_STDEV must equal the dicts edge_detector actually prices with."""

    def test_total_baseline_matches_edge_detector(self):
        assert mc.CURRENT_TOTAL_STDEV == SPORT_TOTAL_STDEV, (
            "model_calibration.CURRENT_TOTAL_STDEV has drifted from "
            "edge_detector.SPORT_TOTAL_STDEV. The calibrator multiplies against "
            "the former while pricing uses the latter, so calibration would be "
            "anchored to a number no longer in use."
        )

    def test_margin_baseline_matches_edge_detector(self):
        assert mc.CURRENT_MARGIN_STDEV == SPORT_MARGIN_STDEV, (
            "model_calibration.CURRENT_MARGIN_STDEV has drifted from "
            "edge_detector.SPORT_MARGIN_STDEV."
        )


class TestCalibrationIsStateless:
    """Each run recomputes from the hardcoded baseline, never from the cache.

    This is what makes raising the cadence safe — corrections cannot compound,
    oscillate, or ratchet. If someone ever rewires `base_stdev` to read the
    previous cache, that property silently disappears.
    """

    @staticmethod
    def _settled(n: int, fair: float, won_frac: float) -> list[dict]:
        rows = []
        for i in range(n):
            rows.append({
                "ticker": "KXMLBTOTAL-26JUL211840MINCLE-13",
                "category": "total",
                "fair_value": fair,
                "_has_fair_value": True,
                "settlement_won": i < int(n * won_frac),
            })
        return rows

    def test_same_input_same_output(self):
        rows = self._settled(40, 0.90, 0.60)
        a = mc._calibrate_one_stdev(rows, "baseball_mlb", 3.45, "total")
        b = mc._calibrate_one_stdev(rows, "baseball_mlb", 3.45, "total")
        assert a == b

    def test_result_scales_with_the_passed_baseline_only(self):
        rows = self._settled(40, 0.90, 0.60)
        one = mc._calibrate_one_stdev(rows, "baseball_mlb", 3.45, "total")
        two = mc._calibrate_one_stdev(rows, "baseball_mlb", 6.90, "total")
        # Doubling the baseline doubles the output: the multiplier is derived
        # from the outcome gap alone, so feeding back a prior result would
        # compound it. Nothing else may enter. Tolerance covers the
        # round(_, 3) each result passes through independently.
        assert two == pytest.approx(one * 2, abs=0.002)

    def test_insufficient_sample_returns_baseline_untouched(self):
        rows = self._settled(mc._MIN_CALIB_SAMPLES - 1, 0.90, 0.60)
        assert mc._calibrate_one_stdev(rows, "baseball_mlb", 3.45, "total") == 3.45


class TestSchedulerWindowClearsTheSampleGate:
    """The weekly job's --days window must be able to reach _MIN_CALIB_SAMPLES.

    `scripts/schedulers/` is gitignored, so this can only assert on a machine
    that has it — skipped elsewhere rather than failing a clean clone.
    """

    BAT = PROJECT_ROOT / "scripts" / "schedulers" / "maintenance" / "calibration.bat"
    # 7 days yielded 17 MLB totals against a bar of 20, at peak MLB volume and
    # with MLB the single most active market. Anything this narrow cannot work.
    MIN_WINDOW_DAYS = 14

    def test_calibration_window_is_wide_enough(self):
        if not self.BAT.exists():
            pytest.skip("scripts/schedulers/ not present (gitignored)")
        text = self.BAT.read_text(encoding="utf-8")
        runs = re.findall(r"model_calibration\.py\s+--days\s+(\d+)([^\r\n]*)", text)
        assert runs, "calibration.bat no longer invokes model_calibration.py --days"
        for days, rest in runs:
            if "--save" not in rest:
                continue  # report-only invocations never touch the stdev cache
            assert int(days) >= self.MIN_WINDOW_DAYS, (
                f"calibration.bat runs --days {days} --save. Windows below "
                f"{self.MIN_WINDOW_DAYS}d cannot accumulate _MIN_CALIB_SAMPLES="
                f"{mc._MIN_CALIB_SAMPLES} settled bets for any (sport, category), "
                "so every sport is skipped and the hardcoded defaults are written "
                "straight back — the C8 loop becomes a silent no-op."
            )


class TestCalibrationDriftPreflight:
    """The pre-wager check that would have caught the 2026-07-31 no-op.

    Age-based checks all reported healthy while the loop wrote defaults back
    every week, so this one recomputes and compares instead.
    """

    @staticmethod
    def _settled(n: int, fair: float, won_frac: float, category="total") -> list[dict]:
        return [{
            "ticker": "KXMLBTOTAL-26JUL211840MINCLE-13",
            "category": category,
            "closed_at": "2026-07-30T00:00:00+00:00",
            "fair_value": fair,
            "_has_fair_value": True,
            "settlement_won": i < int(n * won_frac),
        } for i in range(n)]

    def _cache(self, tmp_path, mlb_total):
        import json
        from datetime import datetime, timezone
        p = tmp_path / "calibration_stdevs.json"
        p.write_text(json.dumps({
            "version": 1,
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "margin_stdev": dict(mc.CURRENT_MARGIN_STDEV),
            "total_stdev": {**mc.CURRENT_TOTAL_STDEV, "baseball_mlb": mlb_total},
        }), encoding="utf-8")
        return p

    def test_flags_a_cache_that_is_behind_the_evidence(self, tmp_path):
        # 40 bets claiming 90% that realized 60% -> the calibrator wants a
        # wider stdev, but the cache still holds the untouched default.
        settled = self._settled(40, 0.90, 0.60)
        health = mc.calibration_drift(
            settled=settled, cache_path=self._cache(tmp_path, mc.CURRENT_TOTAL_STDEV["baseball_mlb"]))
        assert not health["ok"]
        drift = [d for d in health["drifted"]
                 if d["sport"] == "baseball_mlb" and d["category"] == "total"]
        assert drift, "a stale MLB totals stdev must be reported"
        assert drift[0]["expected"] > drift[0]["cached"]

        # And the warning must say age is not the signal, since that is the
        # lesson that made this check necessary.
        text = " ".join(mc.format_drift_warning(health))
        assert "age is NOT the issue" in text
        assert "model_calibration.py" in text

    def test_quiet_when_the_cache_matches_a_recomputation(self, tmp_path):
        settled = self._settled(40, 0.90, 0.60)
        expected = mc._calibrate_one_stdev(
            settled, "baseball_mlb", mc.CURRENT_TOTAL_STDEV["baseball_mlb"], "total")
        health = mc.calibration_drift(settled=settled,
                                      cache_path=self._cache(tmp_path, expected))
        assert health["ok"], health["drifted"]
        assert mc.format_drift_warning(health) == []

    def test_too_few_samples_is_not_drift(self, tmp_path):
        """A legitimate skip recomputes to the baseline, so it must stay quiet.

        This is the false-positive that would make the check unusable: most
        sports are out of season with almost nothing settled.
        """
        settled = self._settled(mc._MIN_CALIB_SAMPLES - 1, 0.90, 0.60)
        health = mc.calibration_drift(
            settled=settled,
            cache_path=self._cache(tmp_path, mc.CURRENT_TOTAL_STDEV["baseball_mlb"]))
        assert health["ok"], health["drifted"]

    def test_missing_cache_is_reported(self, tmp_path):
        health = mc.calibration_drift(settled=[], cache_path=tmp_path / "nope.json")
        assert not health["ok"] and health["cache_missing"]
        assert "never run" in " ".join(mc.format_drift_warning(health))

    def test_audits_against_the_scheduled_window(self):
        """Must match calibration.bat, or out-of-season sports drift forever.

        Caught during development: auditing all-time while the job runs
        --days 30 reported basketball_ncaab/spread as permanently drifted,
        because it has 29 settled bets all-time but far fewer inside 30 days.
        """
        bat = TestSchedulerWindowClearsTheSampleGate.BAT
        if not bat.exists():
            pytest.skip("scripts/schedulers/ not present (gitignored)")
        runs = re.findall(r"model_calibration\.py\s+--days\s+(\d+)([^\r\n]*)",
                          bat.read_text(encoding="utf-8"))
        saving = [int(d) for d, rest in runs if "--save" in rest]
        assert saving and all(d == mc.SCHEDULED_CALIBRATION_DAYS for d in saving), (
            f"calibration.bat saves with --days {saving}, but calibration_drift() "
            f"audits against SCHEDULED_CALIBRATION_DAYS="
            f"{mc.SCHEDULED_CALIBRATION_DAYS}. Mismatched windows make the "
            "preflight report phantom drift for out-of-season sports."
        )
