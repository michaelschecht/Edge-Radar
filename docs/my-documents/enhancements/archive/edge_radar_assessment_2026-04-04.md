# Edge-Radar Assessment
Date: 2026-04-04
Project reviewed: `D:\AI_Agents\Specialized_Agents\Edge_Radar`

## Executive Summary
This review is materially better than the 2026-04-02 assessment. Several of the highest-impact items were genuinely addressed:
- The executor now enforces Kelly-based sizing, per-event caps, concentration caps, and category-specific bet caps in code, not just in docs.
- A real startup validation path exists via `scripts/doctor.py` and it is functional.
- A calibration/reporting workflow now exists via `scripts/kalshi/model_calibration.py`.
- The unified scanner no longer hardcodes a single interpreter path.
The project is in a stronger state than it was two days ago. The remaining issues are narrower, but two of them still matter operationally:
1. Order logging is still request-based rather than fill-based, which can create phantom exposure and distorted P&L if orders rest or partially fill.
2. The docs still overstate how some risk gates behave: concentration and max-bet "gates" are implemented as downsizing, not rejection.
3. The packaging/import/tooling story is still fragile enough that standard repo-root test execution fails without the project-specific venv invocation.

## Verified Improvements Since 2026-04-02

### 1. Runtime risk logic is materially closer to the documented model
This was the biggest issue in the previous review, and it is substantially improved.
Evidence:
- [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L140) now enforces daily loss, position count, edge, score, confidence, duplicate ticker, and per-event caps before sizing.
- [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L202) through [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L239) now apply Kelly sizing plus concentration, max-bet, and bankroll caps.
- [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L364) through [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L401) also track event counts across already-open and newly-approved positions.

### 2. Correlation controls improved
This also improved meaningfully.
Evidence:
- [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L88) through [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L107) now deduplicate correlated bracket bets from the same event/category.
- [`edge_detector.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\edge_detector.py#L1533) through [`edge_detector.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\edge_detector.py#L1538) cap opportunities per game before final ranking.

### 3. Startup validation exists and works
Evidence:
- [`doctor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\doctor.py) checks Python version, venv, credentials, writable directories, config values, API connectivity, and hook installation.
- I ran `D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe scripts\doctor.py` successfully. It connected to Kalshi, parsed 3 Odds API keys, and reported all checks passing aside from a warning about pre-commit hooks.

### 4. Calibration/reporting loop exists
Evidence:
- [`model_calibration.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\model_calibration.py) now computes Brier score, calibration buckets, edge buckets, dimension breakdowns, and recommendations.

### 5. Interpreter hardcoding was partially fixed
Evidence:
- [`scan.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\scan.py#L18) now uses `sys.executable` instead of the previously hardcoded `.venv\Scripts\python.exe` path.

## Findings

### 1. High: trade logging still records requested size/cost even when the order is resting or only partially filled
This is the most important remaining issue because it can corrupt the trade journal, settlement math, and reporting.
Evidence:
- [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L255) through [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L288) always log `contracts = sized.contracts` and `cost_dollars = sized.cost_dollars`, regardless of the actual filled quantity.
- That same record stores `fill_count` from the API, but the requested quantity and requested cost remain the main accounting fields used elsewhere.
- [`kalshi_settler.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py#L93) through [`kalshi_settler.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py#L160) treat any non-error, non-closed trade as unsettled inventory.
- [`kalshi_settler.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py#L59) through [`kalshi_settler.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_settler.py#L80) use `fill_count` when available for payout math, but still use `cost_dollars` from the original log entry.
- [`risk_check.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\risk_check.py#L75) through [`risk_check.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\risk_check.py#L81) and [`risk_check.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\risk_check.py#L272) through [`risk_check.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\risk_check.py#L288) report today's wagered amount from those same logged `cost_dollars` values.
Why it matters:
- A resting GTC order can be logged as if full size was committed immediately.
- A partially filled order can overstate exposure, wagered capital, and later ROI/P&L.
- Settlement and reconciliation become less trustworthy precisely when execution quality matters most.
Recommendation:
- Distinguish clearly between `requested_contracts` / `requested_cost` and `filled_contracts` / `filled_cost`.
- Only treat filled quantity/cost as actual risk capital.
- If an order is resting, either keep it in a separate order log or log it as pending until fills are confirmed.
- Add regression tests for `resting`, `partial fill`, and `zero fill` order responses.

### 2. Medium: the documentation still says concentration and max-bet are reject gates, but the executor silently downsizes and approves them
The runtime behavior is safer than before, but the docs still describe something different from what the code actually does.
Evidence:
- [`ARCHITECTURE.md`](D:\AI_Agents\Specialized_Agents\Edge_Radar\docs\ARCHITECTURE.md#L159) says every order must pass all nine gates and explicitly lists reject conditions for concentration and max-bet size.
- [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L221) through [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L247) do not reject those cases. They resize the order downward and still return `risk_approval="APPROVED"`.
Why it matters:
- Operator expectations and audit interpretation are wrong if the docs imply outright rejection.
- Post-trade review cannot tell whether an order passed cleanly or was force-capped by sizing logic.
Recommendation:
- Pick one model and make it consistent.
- If resizing is the intended behavior, update the docs to say gates 8 and 9 are sizing caps, not reject gates.
- Log whether each approved order was `approved_clean`, `approved_capped_concentration`, or `approved_capped_max_bet`.

### 3. Medium: packaging and test execution are still brittle enough that standard repo-root pytest fails
The project is better than before, but it still depends on import side effects and environment-specific launch paths.
Evidence:
- Running `pytest -q` from the repo root currently fails with `ModuleNotFoundError: No module named 'opportunity'` because [`conftest.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\tests\conftest.py#L4) uses flat imports.
- The suite passes only when invoked with the project venv interpreter: `D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe -m pytest tests -q`.
- Runtime code still depends on sys.path mutation via [`paths.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\shared\paths.py) and side-effect imports like [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L33).
- The Makefile still hardcodes `.venv\Scripts\python.exe` at [`Makefile`](D:\AI_Agents\Specialized_Agents\Edge_Radar\Makefile#L1), and on this Windows PowerShell environment `make` itself was not available.
Why it matters:
- CI portability and contributor onboarding remain fragile.
- The repo still has multiple entrypoint assumptions depending on how it is launched.
Recommendation:
- Either package `scripts/` properly or make `tests/conftest.py` establish the expected import path explicitly.
- Update test docs so the canonical command is unambiguous.
- Remove the remaining environment-specific launcher assumptions from `Makefile` or replace them with a PowerShell-friendly task runner if Windows is the primary platform.

### 4. Low: configuration centralization is still incomplete and currently inconsistent
The repo now has a centralized config module, but it is not the true source of configuration yet.
Evidence:
- [`config.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\shared\config.py#L1) says config is centralized.
- Many key modules still read environment variables directly, including [`kalshi_executor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\kalshi_executor.py#L55), [`risk_check.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\risk_check.py#L41), [`edge_detector.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\kalshi\edge_detector.py#L58), and [`doctor.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\doctor.py#L57).
- The central config also still carries at least one stale default: [`config.py`](D:\AI_Agents\Specialized_Agents\Edge_Radar\scripts\shared\config.py#L19) defaults `MAX_BET_SIZE` to `5`, while `.env.example`, the executor, and the architecture docs treat the prediction default as `100`.
Why it matters:
- The codebase now has two sources of truth: the config module and the direct env reads.
- A stale default in the supposedly central config is exactly the kind of silent drift this refactor was meant to prevent.
Recommendation:
- Either finish the centralization or stop advertising it as done.
- Remove stale defaults from `config.py`, or move all runtime consumers to it and test those values directly.
## Verification Performed
- Read the prior assessment at `D:\AI_Agents\Specialized_Agents\Codex_Skills_Agent\artifacts\edge_radar_assessment_2026-04-02.md`.
- Reviewed the current implementation of `kalshi_executor.py`, `kalshi_settler.py`, `risk_check.py`, `doctor.py`, `scan.py`, `config.py`, `paths.py`, `bootstrap.py`, `odds_api.py`, `edge_detector.py`, and the current tests.
- Ran `D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe -m pytest tests -q` -> `83 passed in 1.40s`.
- Ran `pytest -q` from the repo root -> failed due import-path assumptions in the test harness.
- Ran `D:\AI_Agents\Specialized_Agents\Edge_Radar\.venv\Scripts\python.exe scripts\doctor.py` successfully.

## Overall Assessment
This is a meaningful step forward from the 2026-04-02 state. The project now looks much more like a real operating system for scanning and execution rather than a promising prototype with mismatched docs.
The remaining work is no longer about the headline architecture. It is about execution truth and operational cleanliness:
1. Fix fill-vs-request accounting in the trade journal.
2. Make the docs match the actual sizing/risk semantics.
3. Finish the import/config cleanup so tests and entrypoints are robust without environment-specific assumptions.
If those are tightened, the next review should focus much less on engineering hygiene and much more on realized model quality.
