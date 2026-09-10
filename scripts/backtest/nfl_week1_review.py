"""
nfl_week1_review.py -- S1b: the pre-declared exit from the S1 NFL freeze.

NFL live entries were frozen 2026-08-26 (`MIN_EDGE_THRESHOLD_NFL=1.0`, S1): 26 open
live positions, $28.50 = 31% of a ~$92 bankroll, and **zero** settled NFL history.
The 26 held positions settle across Week 1 of the 2026 season (09-09/09-10, 09-13,
09-14 MNF), so 2026-09-15 is the first morning NFL has ever had evidence.

**The decision is arithmetic, not judgement.** The rule below was written on
2026-08-26, while nothing was at stake, precisely so a hot or cold Week 1 could not
argue with it. This script is the only thing allowed to lift the freeze, it lifts it
only to a capped pilot, and every failure path leaves NFL frozen.

## What is NOT decisive

ROI on those 26 bets. They are legacy entries admitted by a pre-L2 filter (wide
spreads, dead books), so their entry prices contaminate ROI in both directions --
and n=26 could not resolve ROI even if they were clean, when 402 settled bets could
not (bootstrap CI [-6.2%, +36.8%]). It is printed because the operator will want to
see it. It votes on nothing.

## What IS readable at n~26

The model-vs-market Brier head-to-head -- the same test `calibration_study.py` runs,
which the model lost in 6 of 6 months overall (0.2037 market vs 0.2270 model). If
NFL prices better than the Kalshi ask does, that is the strongest signal available
at this sample size. Directional, not conclusive: the bootstrap CI on the difference
is printed and will almost certainly straddle zero at this n. **That weakness is why
branch A unfreezes to a pilot rather than to normal sizing** -- the cap IS the
response to the uncertainty.

## Branches (pre-declared 2026-08-26)

    A  PILOT   model Brier <= market Brier, n >= MIN_SETTLEMENTS, and the model is
               not wildly over-claiming (mean model prob - realised <= MAX_MODEL_ERR)
               -> MIN_EDGE_THRESHOLD_NFL := PILOT_FLOOR (0.08)
    B  FROZEN  market Brier better -- the overall pattern. Stay frozen and re-judge
               on CLV once S8 ships, rather than waiting years for ROI to converge.
    C  FROZEN  anything else: too few settlements, unreadable rows, model badly
               over-claiming, or any exception at all.

**A pilot floor, not an unfreeze.** `MIN_EDGE_THRESHOLD_NFL=0.08` is roughly 2.7x the
global floor, so only strong NFL rows clear Gate 3. It caps how many NFL rows
qualify, not how much money is staked -- but since S4 shipped (2026-08-26) that
second cap does exist: Gate 2b's `MAX_SEGMENT_EXPOSURE_PCT` binds NFL exposure
against equity, live at 0.33. The report states both, in either branch. What
remains true is that Gate 2b runs only at *entry*, so a book already over the
ceiling is not re-checked (S12).

Usage:
    python scripts/backtest/nfl_week1_review.py              # report only, never writes
    python scripts/backtest/nfl_week1_review.py --apply      # apply branch A if it fires
    python scripts/backtest/nfl_week1_review.py --self-check # asserts on the branch logic
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import date
from pathlib import Path

import paths  # noqa: F401  -- adds scripts/shared to sys.path

from calibration_study import bootstrap_ci, brier, load_rows  # noqa: E402
from trade_log import load_settlement_log  # noqa: E402

PROJECT_ROOT = Path(paths.PROJECT_ROOT)
ENV_PATH = PROJECT_ROOT / ".env"
REPORT_DIR = PROJECT_ROOT / "reports" / "Performance"

# ── The pre-declared rule. Changing these numbers after seeing Week 1 defeats
#    the entire point of writing them down on 2026-08-26. ──────────────────────
MIN_SETTLEMENTS = 20      # we expect ~26; below this, no branch can fire
MAX_MODEL_ERR = 0.15      # mean model prob minus realised win rate
PILOT_FLOOR = 0.08        # the capped floor branch A applies (global is 0.03)
FROZEN_FLOOR = 1.0        # what S1 set

ENV_KEY = "MIN_EDGE_THRESHOLD_NFL"


def nfl_rows() -> list[dict]:
    """Settled NFL bets carrying both a model probability and an entry price."""
    return [r for r in load_rows() if r["sport"] == "nfl"]


def _settled_nfl_count() -> int:
    """Settled NFL rows in the settlement log, readable or not."""
    return sum(1 for r in load_settlement_log()
               if str(r.get("ticker", "")).startswith("KXNFL"))


def _segment_cap() -> float | None:
    """The LIVE `MAX_SEGMENT_EXPOSURE_PCT`. None if it cannot be read.

    Read rather than hardcoded on purpose. This report's previous claim about
    S4 was a string literal written before S4 shipped, and it went on asserting
    that no per-sport cap existed for two weeks after one was running at 0.33 --
    inside a report that gates a live-money decision. A number that comes from
    `.env` cannot drift away from `.env`.

    **Loads `.env` first.** Nothing else in this script reads config -- it
    rewrites `.env` as text -- so the dotenv load that every other entry point
    does at import had no reason to exist here. Without it `get_config()` sees
    only the ambient process environment and returns the *code default* (0),
    which reads as "no cap configured" when the live file says 0.33: the same
    false statement this fix exists to remove, arrived at a different way.
    """
    try:
        from dotenv import load_dotenv
        load_dotenv(ENV_PATH)
        from app.config import get_config, reset_config
        reset_config()
        return get_config().risk.max_segment_exposure_pct
    except Exception:                                        # noqa: BLE001
        return None


def _segment_cap_paragraph() -> str:
    """The S4 note, told truthfully for whatever the cap actually is."""
    pct = _segment_cap()
    tail = ("Two caveats hold either way: the pilot floor limits how many rows "
            "qualify, not how much is staked, and **Gate 2b runs only at entry** "
            "-- nothing re-checks a position already held, so a book that drifts "
            "over the ceiling stays there until it runs off (S12).")

    if pct is None:
        return ("`MAX_SEGMENT_EXPOSURE_PCT` could not be read, so this report "
                "cannot say whether a per-sport ceiling is enforcing. **Check "
                "`.env` before acting on this verdict.** " + tail)
    if not pct:
        return ("S4 shipped 2026-08-26, but `MAX_SEGMENT_EXPOSURE_PCT` is **0 "
                "(OFF)** right now -- so **nothing mechanically stops NFL "
                "exposure re-accumulating** the way it did to 31% of bankroll. "
                "Set it before unfreezing, or watch NFL exposure manually. "
                + tail)
    return (f"S4 shipped 2026-08-26, so the per-sport ceiling this script once "
            f"said did not exist is now live: Gate 2b binds NFL exposure at "
            f"**{pct:.0%} of equity**, rejecting when NFL is already at the "
            f"ceiling and trimming an order to the remaining headroom "
            f"otherwise. The 31%-of-bankroll pileup could not repeat silently. "
            + tail)


def roi_context() -> dict:
    """Realised P&L on settled NFL bets. Reported for the operator, votes on nothing.

    **The settlement log's stake field is `cost`, not `cost_dollars`** (fixed
    2026-09-10). Nothing in the log has ever carried `cost_dollars` -- 426 of
    426 rows lack it -- so `staked` summed to exactly $0.00 and `roi` fell
    through its own `if staked else 0.0` guard to a clean-looking **+0.0%**,
    for every possible input, since this script was written. It printed
    `staked $0.00 ROI +0.0%` beside `net $-2.24` on 2026-09-10 without
    complaint. A zero that is indistinguishable from a real result is worse
    than a crash in a report that gates a live-money decision, which is why
    `roi` is now `None` when the stake is unreadable and the caller prints
    `n/a` rather than a number.
    """
    staked = net = 0.0
    wins = n = missing_cost = 0
    for s in load_settlement_log():
        if not str(s.get("ticker", "")).startswith("KXNFL"):
            continue
        n += 1
        # `cost` is the settler's field; `cost_dollars` is the *trade log's*.
        # Both are checked so a row from either shape reads correctly.
        cost = s.get("cost")
        if cost is None:
            cost = s.get("cost_dollars")
        if cost is None:
            missing_cost += 1
        staked += float(cost or 0.0)
        net += float(s.get("net_pnl") or 0.0)
        wins += 1 if s.get("won") else 0
    return {"n": n, "staked": staked, "net": net, "wins": wins,
            "missing_cost": missing_cost,
            "roi": (net / staked) if staked > 0 else None}


def decide(rows: list[dict]) -> dict:
    """Apply the pre-declared branches. Pure function of the settled rows."""
    n = len(rows)
    if n < MIN_SETTLEMENTS:
        # Say how many settled vs how many were USABLE. `rows` counts only
        # settlements carrying a model probability, so a row missing
        # `fair_value` is dropped here silently -- and "too few settlements"
        # then reads as "NFL barely traded" when the real cause may be that
        # the rows exist and are unreadable. On 2026-09-10 the projection for
        # the 09-15 run was 23 usable out of 31 settled: branch A clears its
        # bar by 3, and 8 rows drop out. Which of those two numbers is short
        # changes what the operator should do about it.
        settled = _settled_nfl_count()
        detail = f"only {n} usable settled NFL bets, need {MIN_SETTLEMENTS}"
        if settled > n:
            detail += (f" ({settled} settled, {settled - n} dropped for a "
                       "missing model probability or entry price)")
        return {"branch": "C", "action": "stay_frozen", "n": n,
                "reason": detail}

    ys = [r["y"] for r in rows]
    pm = [r["p_model"] for r in rows]
    pk = [r["p_market"] for r in rows]
    b_model, b_market = brier(pm, ys), brier(pk, ys)
    realised = sum(ys) / n
    model_err = (sum(pm) / n) - realised
    lo, hi = bootstrap_ci(
        rows,
        lambda rs: (brier([r["p_market"] for r in rs], [r["y"] for r in rs])
                    - brier([r["p_model"] for r in rs], [r["y"] for r in rs])),
    )

    base = {"n": n, "brier_model": b_model, "brier_market": b_market,
            "realised": realised, "model_err": model_err,
            "brier_diff": b_market - b_model, "diff_ci": (lo, hi)}

    if b_model > b_market:
        return {**base, "branch": "B", "action": "stay_frozen",
                "reason": (f"market prices NFL better than the model "
                           f"({b_market:.4f} vs {b_model:.4f}) -- the pattern in 6 of 6 "
                           f"months overall. Re-judge on CLV when S8 ships.")}

    if model_err > MAX_MODEL_ERR:
        return {**base, "branch": "C", "action": "stay_frozen",
                "reason": (f"model over-claims by {model_err:+.1%} (claimed "
                           f"{sum(pm) / n:.1%}, realised {realised:.1%}), above the "
                           f"{MAX_MODEL_ERR:.0%} bar -- a good Brier here would be luck, "
                           f"not calibration")}

    return {**base, "branch": "A", "action": "pilot",
            "reason": (f"model Brier {b_model:.4f} beats market {b_market:.4f} over "
                       f"{n} settled bets, model error {model_err:+.1%} within the "
                       f"{MAX_MODEL_ERR:.0%} bar")}


def apply_pilot(env_path: Path = ENV_PATH) -> tuple[bool, str]:
    """Rewrite MIN_EDGE_THRESHOLD_NFL from the freeze value to the pilot floor.

    Fail-closed: refuses unless the key is present and still set to the freeze
    value, so a hand-edit, a re-run, or a partially-applied file is never
    silently clobbered.
    """
    if not env_path.exists():
        return False, f"{env_path} not found -- nothing changed"
    text = env_path.read_text(encoding="utf-8")
    m = re.search(rf"^{ENV_KEY}=([0-9.]+)", text, re.MULTILINE)
    if not m:
        return False, f"{ENV_KEY} not found in .env -- nothing changed"
    current = float(m.group(1))
    if current != FROZEN_FLOOR:
        return False, (f"{ENV_KEY} is {current}, not the {FROZEN_FLOOR} freeze value "
                       f"-- someone changed it already; nothing changed")
    stamp = date.today().isoformat()
    line = (f"{ENV_KEY}={PILOT_FLOOR}"
            f"{' ' * max(1, 32 - len(ENV_KEY) - len(str(PILOT_FLOOR)) - 1)}"
            f"# S1b PILOT {stamp}: Week 1 branch A. Was 1.0 (S1 freeze 2026-08-26).\n"
            f"{' ' * 36}#   Capped lane, ~2.7x the global floor, so only strong NFL rows\n"
            f"{' ' * 36}#   clear Gate 3. This high floor is the ONLY per-sport volume cap\n"
            f"{' ' * 36}#   available until S4 ships -- watch NFL exposure manually.")
    env_path.write_text(text[:m.start()] + line + text[m.end():], encoding="utf-8")
    return True, f"{ENV_KEY}: {FROZEN_FLOOR} -> {PILOT_FLOOR}"


def render(d: dict, roi: dict, applied: str | None) -> str:
    out = [
        "# NFL Week 1 Review (S1b)",
        "",
        f"*Generated {date.today().isoformat()} -- pre-declared rule from 2026-08-26.*",
        "",
        f"**BRANCH {d['branch']} -> {d['action'].upper()}**",
        "",
        d["reason"],
        "",
        "## The readable measure: model vs market Brier",
        "",
    ]
    if "brier_model" in d:
        lo, hi = d["diff_ci"]
        out += [
            "```",
            f"settled NFL bets      {d['n']}",
            f"model Brier           {d['brier_model']:.4f}",
            f"market Brier          {d['brier_market']:.4f}   (lower is better)",
            f"difference            {d['brier_diff']:+.4f}   95% CI [{lo:+.4f}, {hi:+.4f}]",
            f"model mean prob       {d['realised'] + d['model_err']:.1%}",
            f"realised win rate     {d['realised']:.1%}",
            f"model error           {d['model_err']:+.1%}   (bar: <= {MAX_MODEL_ERR:.0%})",
            "```",
            "",
            "The CI will straddle zero at this sample size. That is expected, and it is "
            "why branch A unfreezes to a **capped pilot** rather than to normal sizing.",
            "",
        ]
    out += [
        "## Realised P&L -- reported, NOT decisive",
        "",
        "```",
        f"settled  {roi['n']}   record {roi['wins']}-{roi['n'] - roi['wins']}   "
        f"staked ${roi['staked']:.2f}   net ${roi['net']:+.2f}   "
        + (f"ROI {roi['roi']:+.1%}" if roi["roi"] is not None else "ROI n/a"),
        "```",
        "",
        "These are legacy pre-L2 entries (wide spreads, dead books), so their entry "
        "prices contaminate ROI in both directions, and n is far too small regardless "
        "-- 402 settled bets could not resolve ROI. This number votes on nothing.",
    ]
    if roi["missing_cost"]:
        out += [
            "",
            f"> **{roi['missing_cost']} of {roi['n']} settled NFL rows carry no stake "
            "field**, so `staked` is understated and ROI is computed on only the rows "
            "that do. Until 2026-09-10 this script read `cost_dollars`, which the "
            "settlement log has never written, so the stake read $0.00 and ROI "
            "printed a clean `+0.0%` on every input.",
        ]
    out += [
        "",
        "## Action taken",
        "",
        applied or "None -- report only (`--apply` not passed).",
        "",
        "## Still missing either way",
        "",
        _segment_cap_paragraph(),
    ]
    return "\n".join(out) + "\n"


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="S1b NFL Week 1 freeze review.")
    ap.add_argument("--apply", action="store_true",
                    help="Apply branch A (pilot floor) if it fires. Default: report only.")
    ap.add_argument("--json", action="store_true", help="Emit the verdict as JSON.")
    ap.add_argument("--self-check", action="store_true", help="Run the branch-logic asserts.")
    args = ap.parse_args(argv)

    if args.self_check:
        _demo()
        return 0

    try:
        rows = nfl_rows()
        verdict = decide(rows)
        roi = roi_context()
    except Exception as exc:  # fail closed: any error leaves NFL frozen
        verdict = {"branch": "C", "action": "stay_frozen", "n": 0,
                   "reason": f"review failed ({type(exc).__name__}: {exc}) -- staying frozen"}
        roi = {"n": 0, "staked": 0.0, "net": 0.0, "wins": 0, "roi": 0.0}

    applied = None
    if args.apply and verdict["action"] == "pilot":
        ok, msg = apply_pilot()
        applied = ("**APPLIED** -- " if ok else "**NOT APPLIED** -- ") + msg
        verdict["applied"] = ok
        verdict["applied_msg"] = msg
    elif args.apply:
        applied = f"None -- branch {verdict['branch']} leaves NFL frozen."

    report = render(verdict, roi, applied)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"nfl_week1_review_{date.today().isoformat()}.md"
    path.write_text(report, encoding="utf-8")

    if args.json:
        print(json.dumps({**verdict, "roi": roi, "report_path": str(path)}, default=str))
    else:
        print(report)
        print(f"[saved] {path}")
    return 0


def _demo() -> None:
    """The branch table, exercised. `python nfl_week1_review.py --self-check`."""
    def rows(n, p_model, p_market, wins):
        return [{"sport": "nfl", "p_model": p_model, "p_market": p_market,
                 "y": 1.0 if i < wins else 0.0} for i in range(n)]

    # Too few settlements -> C, whatever the numbers look like.
    assert decide(rows(5, 0.6, 0.5, 5))["branch"] == "C"

    # Model closer to a 60% realised rate than the market -> A.
    good = decide(rows(26, 0.60, 0.40, 16))
    assert good["branch"] == "A" and good["action"] == "pilot", good

    # Market closer -> B, stays frozen.
    bad = decide(rows(26, 0.90, 0.60, 16))
    assert bad["branch"] == "B" and bad["action"] == "stay_frozen", bad

    # Good Brier but the model over-claims badly -> C, not A. A model that says
    # 95% and hits 80% can still beat a market that said 50%; that is luck on the
    # side, not calibration, and it must not lift a money gate.
    over = decide(rows(26, 0.95, 0.50, 19))  # claims 95%, hits 73% -> +22%
    assert over["branch"] == "C", over
    assert "over-claims" in over["reason"], over

    # apply_pilot is fail-closed on every shape of unexpected .env.
    import tempfile
    with tempfile.TemporaryDirectory() as td:
        p = Path(td) / ".env"
        p.write_text("FOO=1\n", encoding="utf-8")
        assert apply_pilot(p) == (False, f"{ENV_KEY} not found in .env -- nothing changed")

        p.write_text(f"{ENV_KEY}=0.08\n", encoding="utf-8")
        ok, msg = apply_pilot(p)
        assert not ok and "not the 1.0 freeze value" in msg, msg

        p.write_text(f"A=1\n{ENV_KEY}=1.0   # frozen\nB=2\n", encoding="utf-8")
        ok, msg = apply_pilot(p)
        assert ok, msg
        text = p.read_text(encoding="utf-8")
        assert f"{ENV_KEY}={PILOT_FLOOR}" in text and "A=1" in text and "B=2" in text
        assert "1.0" not in text.split("\n")[1].split("#")[0]
        # Second run refuses: the value is no longer the freeze sentinel.
        assert not apply_pilot(p)[0]

    print("nfl_week1_review self-check OK")


if __name__ == "__main__":
    sys.exit(main())
