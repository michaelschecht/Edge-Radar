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
