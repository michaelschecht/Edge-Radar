# Edge-Radar Project Improvement Recommendations

*Generated: 2026-03-30*

---

## 1. Standardize CLI Flags Across All Scanners

**Problem:** Execution flags are inconsistent across scripts. `edge_detector.py` and `futures_edge.py` support `--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`, but `prediction_scanner.py` and `polymarket_edge.py` do not. Users have to know to route through `kalshi_executor.py run --prediction` for prediction markets.

**Current state:**

| Flag | `edge_detector` | `futures_edge` | `kalshi_executor` | `prediction_scanner` | `polymarket_edge` |
|------|:--:|:--:|:--:|:--:|:--:|
| `--execute` | Y | Y | Y | **N** | **N** |
| `--unit-size` | Y | Y | Y | **N** | **N** |
| `--max-bets` | Y | Y | Y | **N** | **N** |
| `--pick` | Y | Y | Y | **N** | **N** |
| `--ticker` | Y | Y | Y | **N** | **N** |
| `--save` | Y | **N** | **N** | Y | **N** |
| `--cross-ref` | **N** | **N** | Y | Y | **N** |

**Fix:** Add execution flags (`--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`) to `prediction_scanner.py` and `polymarket_edge.py` using the same pattern already in `futures_edge.py` — import `execute_pipeline` from `kalshi_executor` when execution flags are present. Add `--save` to all scanners. Add `--cross-ref` to `edge_detector.py`.

**Goal:** Every scanner supports the same interface:
```bash
# All of these should work identically:
python scripts/kalshi/edge_detector.py scan --filter mlb --unit-size 1 --max-bets 10 --execute
python scripts/kalshi/futures_edge.py scan --filter nba-futures --unit-size 1 --max-bets 5 --execute
python scripts/prediction/prediction_scanner.py scan --filter crypto --unit-size 1 --max-bets 5 --execute
python scripts/polymarket/polymarket_edge.py scan --unit-size 1 --max-bets 5 --execute
```

**Effort:** Small. The pattern exists in `futures_edge.py` lines 496-506; copy to the two missing scripts.

---

## 2. Standardize Logging

**Problem:** Two different logging patterns are in use:

```python
# Pattern A (newer, preferred) — used in kalshi_executor.py, prediction_scanner.py
from logging_setup import setup_logging
log = setup_logging("script_name")  # Creates logs/script_name.log + console output

# Pattern B (older) — used in edge_detector.py, futures_edge.py, polymarket_edge.py, fetch_odds.py
log = logging.getLogger("module_name")
logging.basicConfig(level=os.getenv("LOG_LEVEL", "INFO"))  # Console only, no file
```

**Fix:** Migrate all scripts to `setup_logging()`. This gives every script a dedicated log file in `logs/` while maintaining console output.

**Files to update:**
- `scripts/kalshi/edge_detector.py`
- `scripts/kalshi/futures_edge.py`
- `scripts/kalshi/fetch_odds.py`
- `scripts/kalshi/fetch_market_data.py`
- `scripts/kalshi/risk_check.py`
- `scripts/polymarket/polymarket_edge.py`
- All `scripts/prediction/*.py` helper modules

**Effort:** Small. Replace 2 lines per file.

---

## 3. Consolidate Import Boilerplate

**Problem:** Every script repeats the same 3-line import preamble:

```python
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "shared"))
import paths  # noqa: F401
from opportunity import Opportunity
```

**Fix:** Make `scripts/shared/paths.py` handle all path setup on import (it mostly does already), then create a single entry point. Options:

- **Option A (minimal):** Add a `scripts/shared/bootstrap.py` that does the path setup + common imports in one line:
  ```python
  from bootstrap import Opportunity, setup_logging, load_dotenv, console
  ```
- **Option B (package install):** Add a minimal `pyproject.toml` or `setup.py` so `scripts/shared/` is an installable package. Then imports are just `from shared.opportunity import Opportunity` with no `sys.path` hacks.

**Recommendation:** Option A for now — keeps things simple while removing repetition.

**Effort:** Medium.

---

## 4. Add `--save` Markdown Reports to All Scanners

**Problem:** The settler report now generates proper markdown (tables, headers, bold values). But the scanner `--save` outputs are JSON watchlists — useful for the pipeline but not for human review. There's no way to save a nicely formatted scan report.

**Fix:** Add a `--save-report` flag (or piggyback on `--save`) that writes a markdown summary of the scan results alongside the JSON watchlist. Pattern:

```
reports/Sports/2026-03-30_mlb_scan.md
reports/Predictions/2026-03-30_crypto_scan.md
reports/Futures/2026-03-30_nba_futures_scan.md
```

This would make it easy to review past scans, email reports, or compare day-over-day.

**Effort:** Medium. The markdown table generation pattern is already in `kalshi_settler.py`.

---

## 5. Add Test Coverage

**Problem:** `pytest` is in `requirements.txt` but there are zero test files. The project has complex probability math (normal CDF, de-vigging, composite scoring) and risk gates that could silently break.

**Priority test targets:**

| Module | What to Test | Why |
|--------|-------------|-----|
| `edge_detector.py` — `consensus_fair_value()` | De-vig math, sharp weighting, edge calculation | Core edge logic; wrong math = bad bets |
| `edge_detector.py` — `spread_cover_prob()`, `total_prob()` | Normal CDF with sport-specific stdev | Regression-prone when tuning stdev values |
| `kalshi_executor.py` — `size_order()` | Risk gates (daily loss, max positions, min edge, confidence) | Must never approve a bet that should be rejected |
| `kalshi_executor.py` — `unit_size_contracts()` | Contract quantity from dollar amount and price | Off-by-one = doubled exposure |
| `futures_edge.py` — `devig_nway()` | N-way probability normalization | Exotic math, easy to break |
| `kalshi_settler.py` — P&L calculation | Net P&L, ROI, CLV | Financial accuracy is non-negotiable |
| `team_stats.py` | API response parsing, fallback behavior | External APIs change formats without notice |
| `sports_weather.py` | Adjustment calculation, dome detection | Wrong adjustments skew all outdoor game edges |
| `line_movement.py` | Sharp signal detection, RLM logic | Core signal; false positives waste money |

**Suggested structure:**
```
tests/
├── test_edge_detection.py
├── test_risk_gates.py
├── test_execution.py
├── test_settlement.py
├── test_team_stats.py
├── test_weather.py
└── test_line_movement.py
```

**Effort:** Large, but high ROI. Start with `test_risk_gates.py` and `test_edge_detection.py` — these protect real money.

---

## 6. Clean Up `strategies/` Directory

**Problem:** CLAUDE.md references `strategies/` with subdirectories (`arbitrage/`, `momentum/`, `value-betting/`, `prediction-market/`) but the directory is empty. Edge detection logic lives in `scripts/` instead.

**Options:**
- **Option A (remove):** Delete `strategies/` and update CLAUDE.md. The project doesn't use a strategy-pattern architecture — edge detection is centralized in the scanners. Keeping an empty directory is misleading.
- **Option B (repurpose):** Use `strategies/` for strategy configuration files (YAML/JSON) that define filter combinations, edge thresholds, and sizing rules per strategy. Example:
  ```yaml
  # strategies/mlb-weather-fade.yaml
  name: MLB Weather Fade
  filter: mlb
  min_edge: 0.03
  require_weather_severity: moderate
  prefer_side: under
  unit_size: 1.00
  max_bets: 5
  ```
  These could be loaded by the scanners via `--strategy mlb-weather-fade` instead of passing 6 flags.

**Recommendation:** Option A for now (clean up), consider Option B later if strategy configurations become complex enough to warrant it.

**Effort:** Small.

---

## 7. Add `MAX_BET_SIZE_SPORTS` to `.env.example`

**Problem:** CLAUDE.md and ARCHITECTURE.md reference `MAX_BET_SIZE_SPORTS=50` but this variable is missing from `.env.example`. Anyone setting up from the template would miss it.

**Fix:** Add to `.env.example` in the Risk Limits section.

**Effort:** Trivial.

---

## 8. Unify Report Output Format

**Problem:** Different parts of the system save output in different formats:

| Script | `--save` Output | Format |
|--------|-----------------|--------|
| `kalshi_settler.py report` | `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.md` | Markdown (just fixed) |
| `edge_detector.py scan` | `data/watchlists/kalshi_opportunities.json` | JSON |
| `prediction_scanner.py scan` | `data/watchlists/prediction_opportunities.json` | JSON |
| `daily_sports_scan.py` | `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md` | Markdown |
| `futures_edge.py` | (no save option) | N/A |

**Fix:** Establish a convention:
- **`data/watchlists/`** — Machine-readable JSON (for pipeline consumption). Keep as-is.
- **`reports/`** — Human-readable markdown. Every `--save` flag should also write a markdown report here with proper tables.
- Add `--save` to `futures_edge.py` and `polymarket_edge.py`.

**Effort:** Medium.

---

## 9. Consolidate Script Entry Points

**Problem:** There are 5 different scripts a user might run to scan markets, each with slightly different interfaces:

```bash
python scripts/kalshi/edge_detector.py scan --filter mlb        # Sports
python scripts/kalshi/futures_edge.py scan --filter nba-futures  # Futures
python scripts/prediction/prediction_scanner.py scan --filter crypto  # Prediction
python scripts/polymarket/polymarket_edge.py scan                # Polymarket
python scripts/kalshi/kalshi_executor.py run --filter mlb        # Unified (but different flags)
```

**Fix:** Consider a single entry point that routes to the right scanner:

```bash
python scripts/scan.py sports --filter mlb --unit-size 1 --max-bets 10
python scripts/scan.py futures --filter nba-futures
python scripts/scan.py prediction --filter crypto --cross-ref
python scripts/scan.py polymarket
```

This doesn't replace the individual scripts (they'd still work for direct use), but gives users one command to remember. `kalshi_executor.py run` is halfway there already — it has `--prediction` and `--from-file` — but it doesn't cover futures or polymarket.

**Effort:** Medium. Most wiring already exists.

---

## 10. Documentation Cleanup

### 10a. SCRIPTS_REFERENCE.md is out of date
The new flags added to `edge_detector.py` (`--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`) are not reflected in `SCRIPTS_REFERENCE.md`. This doc should be regenerated from `--help` output after all CLI standardization is done.

### 10b. CLAUDE.md `strategies/` reference
Remove or update the `strategies/` section if the directory is cleaned up (see item 6).

### 10c. MLB_FILTERING_GUIDE.md cross-references
The new MLB guide references enhancement priorities (pitcher data, bullpen tracking) that should link to `EDGE_OPTIMIZATION_ROADMAP.md`.

### 10d. Consolidate the 3 betting guides
`SPORTS_GUIDE.md`, `FUTURES_GUIDE.md`, and `PREDICTION_MARKETS_GUIDE.md` have overlapping sections (edge model explanation, risk gates, CLI examples). Consider a shared "How Edge Detection Works" section referenced by all three, reducing duplication.

**Effort:** Small-Medium.

---

## 11. Add Pre-Commit Hooks

**Problem:** `pre-commit` is in `requirements.txt` but there's no `.pre-commit-config.yaml`. CLAUDE.md mentions "pre-commit hooks to prevent key leakage" but they're not configured.

**Fix:** Add `.pre-commit-config.yaml` with:
- `detect-secrets` — Catches accidentally committed API keys
- `black` — Consistent formatting
- `flake8` — Lint errors
- `check-json` — Validates JSON data files
- `no-commit-to-branch` — Prevent direct pushes to master

**Effort:** Small.

---

## 12. Add a `Makefile` or `justfile`

**Problem:** Common workflows require long commands that are easy to forget:

```bash
python scripts/kalshi/edge_detector.py scan --filter mlb --unit-size 1 --max-bets 100
python scripts/kalshi/kalshi_settler.py report --detail --save
python scripts/schedulers/run_schedulers.py --list
```

**Fix:** Add a `Makefile` (or `justfile`) with common targets:

```makefile
scan-mlb:
	python scripts/kalshi/edge_detector.py scan --filter mlb --unit-size 1 --max-bets 100

scan-all:
	python scripts/kalshi/edge_detector.py scan --top 25

report:
	python scripts/kalshi/kalshi_settler.py report --detail --save

settle:
	python scripts/kalshi/kalshi_settler.py settle

risk:
	python scripts/kalshi/risk_check.py

status:
	python scripts/kalshi/kalshi_executor.py status
```

**Effort:** Small.

---

## Priority Order

| # | Item | Impact | Effort | Priority |
|---|------|--------|--------|----------|
| 1 | Standardize CLI flags across scanners | High | Small | **Do first** |
| 5 | Add test coverage (risk gates + edge math) | High | Large | **Do first** |
| 2 | Standardize logging | Medium | Small | **Quick win** |
| 7 | Add `MAX_BET_SIZE_SPORTS` to .env.example | Low | Trivial | **Quick win** |
| 11 | Pre-commit hooks | Medium | Small | **Quick win** |
| 10 | Documentation cleanup | Medium | Small | **Do after #1** |
| 6 | Clean up strategies/ | Low | Small | **Housekeeping** |
| 3 | Consolidate import boilerplate | Low | Medium | **Nice to have** |
| 8 | Unify report output format | Medium | Medium | **Next sprint** |
| 4 | Markdown scan reports | Medium | Medium | **Next sprint** |
| 12 | Makefile | Low | Small | **Nice to have** |
| 9 | Unified scan entry point | Medium | Medium | **Future** |
