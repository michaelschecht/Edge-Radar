# Changelog

---

## 2026-04-27 -- Polymarket integration removed

### Why

Zero historical use evidenced. No `data/polymarket/`, no `reports/Polymarket/`, no scheduled tasks ever ran the polymarket subcommand. Prediction-market betting is gated off by default (`ALLOW_PREDICTION_BETS=false`, R25), and the Polymarket cross-reference branch in `prediction_scanner.py` was carrying ~350 lines of decision logic for a code path nothing exercised. Decision: full delete now, recoverable via git history if the use case revives.

### Code removed

- **Deleted:** `scripts/polymarket/` (entire directory — `__init__.py` + 872-line `polymarket_edge.py`)
- **Deleted:** `.claude/skills/polymarket/` (SKILL.md + 9 reference files)
- **Deleted:** `prompts/polymarket/` (`cross-reference-scan.md`, `crypto-arbitrage.md`)
- **Deleted:** `docs/scripts/polymarket_edge.md`
- **Stripped from `scripts/scan.py`:** `polymarket` subcommand registry entry; `poly`/`xref` aliases; example/help-text mentions
- **Stripped from `scripts/prediction/prediction_scanner.py`:** `polymarket_edge` import block; `cross_ref` parameter on `scan_prediction_markets`; `polymarket`/`poly`/`xref` filter shortcuts; the standalone xref scan branch + the per-opportunity Polymarket enrichment loop (~70 lines); `--cross-ref` CLI flag; `is_poly_filter` dispatch logic in `main()`
- **Stripped from `scripts/kalshi/fetch_market_data.py`:** `POLYMARKET_URL` constant; `fetch_polymarket_markets()`; `fetch_polymarket_orderbook()`; `--source polymarket` choice; default flipped from `polymarket` to `kalshi`
- **Stripped from `scripts/shared/paths.py`:** `POLYMARKET_DIR` constant + sys.path entry
- **Stripped from `scripts/shared/report_writer.py`:** `polymarket` key in `REPORT_DIRS`
- **Stripped from `scripts/schedulers/automation/telegram_bot.py`:** `--cross-ref` flag in `/scan prediction`
- **Stripped from `webapp/services.py`:** `scripts/polymarket` from sys.path; `cross_ref` parameter on `run_scan`; `cross_ref` plumbed through to `scan_prediction_markets`
- **Stripped from `webapp/views/scan_page.py`:** `cross_ref` defaults; "Cross-Ref Polymarket" checkbox; `cross_ref` in favorite save state and the service-layer call
- **Stripped from `Makefile`:** `scan-polymarket` target; `scan-polymarket` from `scan-all`; help-text and `.PHONY` entries
- **Stripped from `requirements.txt`:** commented `py-clob-client` line
- **Stripped from `pyproject.toml`:** `scripts/polymarket` from pytest `pythonpath`

### Docs updated

- `CLAUDE.md` — removed Polymarket from "Planned" section; removed `polymarket/` from the project tree; removed `polymarket-py` from the key-libraries list
- `README.md` — dropped "Polymarket cross-ref" bullet from supported markets, "Polymarket Cross-Reference" section, polymarket dir from tree, `polymarket-py` mention in description, "Polymarket" data-sources row
- `docs/ARCHITECTURE.md` — removed Polymarket cross-market row from prediction model table
- `docs/SCRIPTS_REFERENCE.md` — removed polymarket from goal table, scanner registry, alias resolution mermaid + alias table, scanner subgraph, `--cross-ref` tip, examples; flipped `fetch_market_data --source` default from polymarket to kalshi
- `docs/setup/SETUP_GUIDE.md` — dropped Polymarket from free-API list, data-sources table, external-docs links
- `docs/web-app/LOCAL.md` — removed `scripts/polymarket/*.py` from architecture diagram, Cross-Ref filter row, Polymarket-via-CLI note
- `docs/mcp-config/mcp-servers.md` — removed `POLYMARKET_PRIVATE_KEY` env line, polymarket-mcp future-integration row, Polymarket fetch examples
- `docs/scripts/prediction_scanner.md` — full rewrite without `--cross-ref` references
- `.claude/skills/edge-radar/SKILL.md` — multiple sections cleaned: description frontmatter, flag table, scanner table, makefile shortcuts, polymarket subsection, scan-and-bet block, routing examples
- `prompts/predictions/full-prediction-execute.md` — full rewrite (Polymarket cross-ref was central)
- `prompts/predictions/{execute-predictions,crypto-edge-scan,scan-all-predictions}.md` — removed cross-ref blocks
- `prompts/portfolio/morning-routine.md` — removed step 7 + cross-market brief item

### Known stale (not edited — flagging for future refresh)

- `.claude/images/diagrams/**/*.{mmd,svg}` — data-flow diagrams still depict the Polymarket node; will need regeneration if/when diagrams are next refreshed.
- `.claude/html/{index.html,index2.html,dataflow.html}` and `docs/my-documents/HTML-Interactive-Pages/Edge-Radar-Only/index2-*.html` — interactive visualizations include Polymarket; same status as the Mermaid diagrams.
- `docs/my-documents/temp/archive/*` and `docs/my-documents/repo-analysis/edge_radar_repository_analysis_2026-04-22.md` — point-in-time snapshots; intentionally left as-is to preserve the historical record.

### Validation

- `pytest tests/` passing (no tests referenced polymarket).
- `python scripts/scan.py --help` no longer lists polymarket.
- `python scripts/scan.py prediction --help` no longer carries `--cross-ref`.

### Recovery path

Polymarket integration can be restored from `git show <commit-before-removal>:scripts/polymarket/polymarket_edge.py` — but if/when revisited, treat as a fresh design (Polymarket Gamma/CLOB APIs evolve, a current-state implementation will likely be more useful than reverting).

---

## 2026-04-25 -- Config centralization Phase 3 (lint guard against regression)

### `scripts/lint/check_config_centralization.py`

Replaces the original "simple grep" idea from the spec with a small Python script — necessary because the rule needs nuance the raw grep can't express.

**What it does:**
- Walks `app/`, `scripts/`, `webapp/` for `os.getenv` / `os.environ`.
- Excludes `app/config.py` (the single source of truth), `scripts/custom/` (user automation), and `scripts/lint/` itself (this script names the forbidden strings to communicate the rule).
- Skips comment-only lines.
- Skips lines tagged `# config-bootstrap` — reserved for the 4 Streamlit secrets-bootstrap lines in `webapp/services.py` (lines 69, 71, 75, 77 now carry the annotation inline).
- Exits 1 on any violation, 0 otherwise. Output names file, line, content, and tells the contributor what to do.

### Wired into automation

- `make lint-config` Makefile target.
- `.pre-commit-config.yaml` local hook with `pass_filenames: false` and `always_run: true` so the lint sees the whole tree, not just staged files (a sneaky violation in an unstaged file would otherwise slip through).

### Unit tests — 5 new tests in `tests/test_lint_config_centralization.py`

1. The current production codebase passes the lint cleanly.
2. A regression — adding `os.getenv("FOO")` to a previously clean file — is detected.
3. The `# config-bootstrap` annotation correctly suppresses violations.
4. Comment-only lines mentioning `os.getenv` textually are ignored.
5. `app/config.py` is unconditionally excluded.

**Final test count: 297 passing** (292 from earlier phases + 5 lint tests). Production-code `os.getenv` reads outside `app/config.py`: 0.

---

## 2026-04-25 -- Config centralization Phase 2 — all 8 script groups migrated

### What changed

Mechanical migration of every `os.getenv` config read across the production codebase to `app.config.get_config()`. Per-step breakdown:

| Step | Files | Calls removed |
|:----:|:------|:-------------:|
| 1 | `scripts/doctor.py` | 9 |
| 2 | `scripts/kalshi/risk_check.py` | 5 |
| 3 | `scripts/kalshi/kalshi_client.py` | 8 |
| 4+6 | `scripts/kalshi/edge_detector.py`, `scripts/kalshi/fetch_odds.py` | 1 + 2 |
| 5 | `scripts/kalshi/kalshi_executor.py` | 23 |
| 7 | `prediction_scanner.py`, `backtester.py`, `logging_setup.py`, `odds_api.py`, `fetch_market_data.py`, `telegram_bot.py` | 11 |
| 8 | `webapp/services.py` (6 reads — bootstrap retained) | 6 |

**Final tally: 65 reads removed, 0 outside `app/config.py`.** The 4 `os.environ` writes in the `webapp/services.py` Streamlit secrets bootstrap are deliberately retained — they're the input side of cfg, not config consumption.

### Notable per-file details

- **`doctor.py`:** display normalization is the only user-visible change (`UNIT_SIZE=.50` previously rendered as `$.50`; now `$0.50` via explicit `:.2f` format). Numeric values reaching every gate are byte-identical.
- **`risk_check.py`:** dropped a dead `MIN_EDGE` constant that no caller imported.
- **`kalshi_client.py`:** Streamlit-secrets timing preserved — all reads happen at instantiation, not import. The `st.secrets["kalshi"]["private_key"]` fallback in `_resolve_key_content` is kept as a backup for direct Streamlit-app use that bypasses `services.py`. Phase 1 default for `KalshiCredentials.private_key_path` tweaked from `"keys/live/kalshi_private.key"` to `""` to mirror the original `os.getenv("KALSHI_PRIVATE_KEY_PATH", "")` runtime default; preserves byte-identical "credentials not configured" error path when env is unset. `.env.example` unchanged.
- **`kalshi_executor.py`:** all 21 module-level risk constants and the per-sport edge-override dict source from `_cfg = get_config()`. Constants stay as plain mutable globals because `tests/test_risk_gates.py` mutates them directly (`kalshi_executor.MAX_OPEN_POSITIONS = 10`) — only the *initial source* changed. Two in-function `DRY_RUN` reads (resting-order janitor + execute-table title) use `get_config().system.dry_run` against the memoized cache.
- **`fetch_odds.py`, `fetch_market_data.py`, `telegram_bot.py`:** API-key constants use `cfg.X or None` to preserve `None`-on-unset semantics from the original `os.getenv("X")` — matters where credentials get spliced into HTTP headers and URL f-strings (`None` and `""` render differently).
- **`logging_setup.py`:** `from app.config import get_config` placed *after* `load_dotenv()` so `.env` values are in `os.environ` before the first cfg read.
- **`webapp/services.py`:** module-level constants (imported by `views/scan_page.py` and `views/portfolio_page.py`) sourced from `_cfg = get_config()`. `reset_config()` defensive call added between the secrets bootstrap and downstream imports — explicit contract that any code mutating `os.environ` after potentially priming the cache uses this seam. Bug found and fixed: Streamlit's `webapp/app.py` puts `webapp/` on `sys.path[0]`, which made `from app.config import …` resolve to `webapp/app.py` (a file) instead of the `app/` package. Resolved by explicitly inserting `PROJECT_ROOT` at `sys.path[0]` inside `services.py` after the script-subdir loop. Documented inline.

### Infra side-fix

`scripts/shared/paths.py` and `.venv/Lib/site-packages/edge_radar.pth` both now prepend `PROJECT_ROOT` to `sys.path` so `from app.config import get_config` resolves in any script that imports `paths`. Without this, every migrated script would need its own ad-hoc `sys.path.insert(0, str(PROJECT_ROOT))`.

### Out of scope (flagged, not migrated)

- `scripts/custom/Python/send_daily_email.py` uses `os.environ["AGENTMAIL_API_KEY"]` — user-automation script, knob not documented in `.env.example` or core docs. Migrating it would add a non-core knob to `app/config.py`, violating the "no new knobs" non-goal.

All 292 tests still pass after the migration.

---

## 2026-04-25 -- Config centralization Phase 1 (refactor scaffolding)

### `app/config.py` — typed config module landed (no script migrations yet)

- **Why:** Audit found 75 `os.getenv` calls across 14 files, with `MIN_EDGE_THRESHOLD` read in 5 places using two type styles (string `"0.03"` vs float `0.03`) and `DRY_RUN` coerced inconsistently. Tracked under `docs/my-documents/enhancements/CONFIG_CENTRALIZATION.md`.
- **What landed:** `app/config.py` with 10 frozen dataclasses (Kalshi creds, Kalshi-prod creds, OddsApi creds, Alpaca creds, Telegram creds, RiskLimits, GateThresholds, KellyConfig, PerSportOverrides, System). Each has `from_env()` for one-shot coercion; aggregate `Config.from_env()` runs `validate()`. Memoized via `get_config()` / `reset_config()`. 32 unit tests in `tests/test_config.py`.
- **What did NOT change:** No existing script touched. `os.getenv` count unchanged. `.env.example` unchanged. No behavior change of any kind. Phase 2 (mechanical migration of 8 script groups) is a separate set of commits.
- **Discrepancies flagged for a future doc-reconciliation PR (not fixed here):** `MAX_OPEN_POSITIONS` is `10` in code/CLAUDE.md but `50` in `.env.example`; `MAX_PER_EVENT` is `2` in code/`.env.example` but `3` in CLAUDE.md. Phase 1 followed code as source of truth.

---

## 2026-04-24 (PM) -- Scanner Parity, Futures Bug Hunt, Prediction-Market Audit (R17, R18, R20, R21, R22, R23, R24a, R25)

### R17. Scanner flag parity (`--budget`, `--report-dir`)
- **Problem:** User tried `futures_edge.py scan --exclude-open --budget 5%` and discovered that `--budget` and `--report-dir` were sports-only. Futures / prediction / polymarket CLIs didn't accept them, and even if they had, `execute_pipeline(budget=…)` wasn't threaded through. Risk-gate logic itself was already uniform (all four call `execute_pipeline`).
- **Fix:** Extracted `parse_budget_arg()` into `kalshi_executor.py` so all four scanners share the same `"10%"` / `"15"` / `"0.15"` / `"150"` parsing contract. Added `--budget` + `--report-dir` to futures / prediction / polymarket argparse; wired each to `execute_pipeline(budget=…)` and `save_scan_report(output_dir=…)`. Sports scanner's inline 7-line budget block replaced with the shared helper.

### R21. `dedup_correlated_brackets` now passes futures through unchanged
- **Problem:** A futures scan of 20 opportunities was being collapsed to 2 before risk gates even ran. `dedup_correlated_brackets` grouped by `(event_key, category)`; for championship futures `KXNBA-26-LAL` / `KXNBA-26-BOS` / `KXNBA-26-OKC` all share event key `KXNBA-26`, so dedup saw 16+ team outcomes as one "alt-line bracket" and kept only the top composite score.
- **Fix:** When `opp.category == "futures"`, use the full ticker as the dedup key so each outcome survives. Correct for alt-line brackets ("Over 221.5" / "Over 224.5") that are genuinely correlated, wrong for futures where each team is a distinct independent bet. Concentration still bounded by Gate 6 (`MAX_PER_EVENT=2`).

### R22. `FUTURES_MAP` prefix-collision + semantic-mismatch double bug
- **Problem:** Futures scan surfacing "+30-75% edge" on basically every MLB team — too good to be true, and it was. Two compounding bugs: (1) **Prefix collision** — iteration broke on first `ticker.startswith(prefix)` match, so `KXMLBPLAYOFFS-26-LAD` matched the `KXMLB` entry first. Same silently affected `KXNBAEAST`/`KXNBAWEST`/`KXNHLEAST`/`KXNHLWEST`. (2) **Semantic mismatch** — even with prefix ordering fixed, those 5 derivative entries pointed to championship-winner odds while representing playoff-qualification or conference-winner questions. LAD's probability to **make playoffs** (~95%) is fundamentally different from LAD's probability to **win the World Series** (~28%).
- **Fix:** Switched matching from `ticker.startswith(prefix)` to exact series extraction (`ticker.split("-", 1)[0]` lookup). Removed the 5 semantically-broken entries from `FUTURES_MAP` with a comment explaining why each needs a proper data source before being re-added (tracked in R19). Updated `FUTURES_FILTER_SHORTCUTS` to match.
- **Verification:** Same scan went from 45 bogus opportunities at +30-75% edge → 2 real opportunities at +4% edge (OKC NBA Finals, LAD World Series). Modest edges are what a sharp futures market should look like.

### R23. Robust Odds API key rotation + persistent quota cache
- **Problem:** `--filter mlb-futures` returned "No outright data" despite unfiltered scan working seconds earlier. Live probe showed first 5 of 10 keys exhausted (500/500 used each). Two compounding bugs: (1) `futures_edge.fetch_outrights` used `for attempt in range(3)`, so after keys 0-2 all 401'd the retry loop exited before reaching the healthy key at index 5. (2) `_remaining` dict was process-local — every fresh invocation rediscovered exhaustion the hard way.
- **Fix:** Replaced `range(3)` in `fetch_outrights` with the `tried: set[str]` loop pattern used in `edge_detector.fetch_odds_api` (cycles through every configured key). Added `mark_exhausted()` called on 401 responses. Persistent quota cache at `data/cache/odds_api_quota.json` — `_remaining` loaded at `_load_keys()` time, saved on every `report_remaining()` / `mark_exhausted()`. `get_current_key()` now auto-advances past keys with cached `remaining == 0`. Fallback: if every key is cached exhausted, return the current slot anyway so a monthly quota reset can be re-discovered.
- Env: nothing new — uses existing `ODDS_API_KEYS`.

### R24a. Webapp scan cache (`@st.cache_data(ttl=60)`)
- **Problem:** Zero `@st.cache` decorators existed anywhere in `webapp/` before this. Every scan-button click fired a fresh Odds API fetch, and exploratory "try a filter, scan, change filter, scan again" sessions burned requests fast. Investigation under R24 surfaced this as one contributor to F31's 175-requests-in-5-min burn rate.
- **Fix:** Added 60s TTL cache on `run_scan()` keyed on all scan parameters (market_type, ticker_filter, category, date, min_edge, top_n, exclude_open, cross_ref). Client param renamed `client` → `_client` per Streamlit convention for unhashable args. CLEAR button now also calls `run_scan.clear()` so the user can force a refresh on demand.

### R18. Scan tables show "Gate" column previewing executor rejects
- **Problem:** User ran `scan --filter mlb-futures --unit-size .5` and got "No opportunities passed risk checks" (LAD rejected on composite score 4.6 < 6.0). Same command without `--unit-size` happily listed LAD as a +4.3% edge row with no indication it would fail. Scan table promised an opportunity the system would never take.
- **Fix:** Added `preflight_gate_status(opp)` helper in `kalshi_executor.py` that checks the 5 static per-opportunity gates and returns a short label: `"ok"` / `"edge"` / `"price"` / `"score"` / `"conf"` / `"no-fav"` / `"pred-off"`. Wired into the scan-table render path of all four scanners. Green "ok" for pass, red label for the failing gate. Runtime gates (daily loss, position count, duplicate ticker, per-event cap, series dedup) require live portfolio state and are NOT checked here — `"ok"` is necessary but not sufficient.

### R20. Prediction-market audit
- **Findings:** Zero prediction-market bets in 173 historical settlements. All 6 modules (crypto / weather / spx / mentions / companies / politics) cache live data with no TTL. 4 of 6 modules have zero unit tests. Live scans produce obvious garbage: crypto +80% "edges" on 4¢ tail bets, weather showing $1.00 fair values on 1°F range markets (one was ready to execute at HIG confidence, 9.7 composite, one `--unit-size` away). `DEMO_KEY` hardcoded in `companies_edge.py`.
- **Prescription:** Safety-gate the category via R25. Rebuild (R25b/R25c) before any M1-M4 upgrades.

### R25. New Gate 4.7 — prediction-market safety gate
- **Fix:** New reject gate in `size_order()` — rejects opportunities where `opp.category in {"crypto", "weather", "spx", "mentions", "companies", "politics"}` unless `ALLOW_PREDICTION_BETS=true`. Default off. `preflight_gate_status()` returns `"pred-off"` so the R18 Gate column surfaces the rejection at scan time.
- Env: `ALLOW_PREDICTION_BETS=false` added to `.env.example`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, webapp secrets passthrough.

### Gate Numbering
- **Total gates:** 13 (was 12). Reject gates 1-7 (including 3.5, 4.5, 4.6, 4.7); sizing caps 8-9.

### Tests
- 38 new tests across the session: 5 for `TestDedupCorrelatedBrackets` (R21), 7 for `TestFuturesSeriesMatch` (R22), 13 for `tests/test_odds_api.py` (R23), 9 for `TestPreflightGateStatus` (R18), 4 for the prediction safety gate (R25). 218 → 260 passing.

---

## 2026-04-24 -- 30-Day Calibration Cycle (R12, R13, R14, R15, R16)

### 30-Day Review (160 settled trades since 2026-03-25)
- **Sample:** 160 settled, 80W-80L (50%), +37.4% ROI ($43.48 P&L), Brier 0.2657. Aggregate remains healthy but concentrated: NHL +72% and NCAAB +71% carry most of the P&L; a single 7¢ MLS fill (04-20 +$14.80) is a third of the absolute P&L on its own.
- **F14 — High-confidence WR < Medium:** High 47% WR (n=57) vs Medium 53% WR (n=100). High ROI only wins via larger per-bet sizing. NBA instance is the loudest: High = 1-6 / -71% ROI.
- **F15 — NBA negative across three review windows:** 30d -14.8% (n=17), 14d -26%, post-baseline -15%. R2 stdev bump (04-21) too recent to attribute.
- **F17 — Calibration overconfidence persists 50-100%:** -14 to -22pp gap on every non-longshot probability bucket.
- **F21 — `model_calibration.py` blind to real sample:** Script read `trade_log` (16 entries, 3 closed) instead of `kalshi_settlements.json` (173 entries). R12 was impossible to run until fixed.
- **F22 — Live `.env` missing per-sport edge overrides:** For the entire post-baseline window, NBA and NCAAB were running at the 3% global floor, not the documented 8% / 10%. Silent drift — `.env.example` had them but the live env did not.

### R15. `model_calibration.py` points at settlement source
- **Fix:** New `_load_settled_trades()` normalizer reads `data/history/kalshi_settlements.json` (same source `betting_analysis.py` uses). Maps `cost` → `cost_dollars`, `won` → `settlement_won`, `settled_at` → `closed_at`; derives `category` from ticker via `bet_type_from_ticker()`. Replaces string-based ISO cutoff comparison with `datetime` parsing that tolerates trailing `Z`. All downstream helpers (`_brier_score`, `_calibration_buckets`, `_edge_bucket_stats`, `_dimension_stats`, cross-tab, recommendations) unchanged.
- Files: `scripts/kalshi/model_calibration.py`.

### R12. First full-sample calibration report
- **First run:** `reports/Calibration/2026-04-24_calibration_report.md`. 10 prioritized recommendations (2 HIGH, 8 MEDIUM). Brier 0.2657 (worse than coin-flip).
- **Per-sport Brier surfaces NBA as the worst-calibrated sport:** NBA 0.3306, NCAAB 0.2885, MLB 0.2519, NHL 0.2376 (NHL better than coin-flip — model is calibrated there), MLS 0.2364 (small sample).
- **Cross-tab insight:** medium × Total is the bread-and-butter combo (+46% ROI on n=71); high × Total is -52% on n=4 (tiny); high × ML is roughly flat at +10%.
- **Edge-bucket inversion softening:** 25%+ bucket 14d -24% ROI → 30d +16% ROI. Suggestive evidence R2 is working; needs another window + post-R13/R14 settlements to confirm.

### R14. `MIN_EDGE_THRESHOLD_NBA` bumped 0.08 → 0.12 (+ live-env override restore)
- **Fix:** NBA per-sport floor raised to 12%. Also added both `MIN_EDGE_THRESHOLD_NBA=0.12` and `MIN_EDGE_THRESHOLD_NCAAB=0.10` to the live `.env` — they were documented in `.env.example` and `CLAUDE.md` but missing from the actual env file, so both were silently falling back to the 3% global floor.
- **Scope intentionally minimal:** 17-bet NBA sample showed the bleed was concentrated in High-confidence picks (1-6, -71% ROI) and 2/3 of the NBA ML losers were sub-10¢ lottery tickets already caught by R7. Playoff-specific stdev and "NBA Totals-only" filters explicitly rejected — not enough sample. Confidence-tier fix lives in R13.
- Env: `MIN_EDGE_THRESHOLD_NBA=0.12`. Files: `.env`, `.env.example`, `CLAUDE.md`, `docs/ARCHITECTURE.md`, `docs/setup/SETUP_GUIDE.md`, `docs/web-app/CLOUD.md`, `docs/scripts/kalshi_executor.md`, `docs/kalshi-sports-betting/MLB_FILTERING_GUIDE.md`, `.claude/html/index.html`, `scripts/kalshi/kalshi_executor.py` (docstring).

### R13. Confidence bumps are now one-way (down only)
- **Problem:** `_adjust_confidence_with_stats()` applied ±1 tier bumps from three call sites (team stats, rest/B2B, sharp money). 30-day data showed upward bumps correlated with inflated claimed edge but worse realized outcomes — High-confidence WR 47% < Medium 53% portfolio-wide, NBA High at 1-6 / -71% ROI.
- **Fix:** `contradicts` still drops a tier; `supports` is now a no-op. All three call sites share the function, so the change applies uniformly. Base "high" tier remains reachable via the book-count rule (≥8 sharp books + tight consensus <5%) — only the bolt-on bumps are neutralized. Kelly sizing unaffected (sizing doesn't use confidence directly); composite score naturally compresses; Gate 4.6's confidence=high requirement naturally tightens — correct direction.
- No env var. +4 regression tests (`TestConfidenceBumpsOneWay`) → 222 passing.
- Files: `scripts/kalshi/edge_detector.py`, `tests/test_edge_detection.py`.

### R16. Monthly calibration cron
- **Fix:** New `calibration` profile in `install_windows_task.py` runs `model_calibration.py --days 30 --save` on day 1 of each month at 02:00 (after nightly settler). Required extending the installer to support `MONTHLY` schedules with `/D` day specifier; daily profiles unchanged.
- **Also:** Narrowed `scripts/schedulers/` gitignore so the portable `automation/` folder is now tracked (three `.py` files — all paths derive from `__file__`, secrets via `.env`, no machine-specific state). Sibling scheduler folders with hardcoded-path `.bat` files stay gitignored.
- Install: `python scripts/schedulers/automation/install_windows_task.py install calibration`.
- Files: `scripts/schedulers/automation/install_windows_task.py`, `scripts/schedulers/automation/daily_sports_scan.py`, `scripts/schedulers/automation/telegram_bot.py`, `docs/setup/AUTOMATION_GUIDE.md`, `.gitignore`.

### Gate Numbering
- **Total gates:** 12 (unchanged since R7).

---

## 2026-04-22 -- Repo-Analysis Response + Lottery-Ticket Floor (Q1-Q5, R7)

### Repo Analysis Response (2026-04-22 independent review)
- **Q1. Web app `market_type` wired through service layer.** UI exposed sports/futures/prediction/polymarket but `webapp/services.py run_scan()` had no `market_type` param — everything routed into `scan_all_markets` (sports-only). `run_scan()` now dispatches to `scan_all_markets` (sports), `scan_futures_markets` (futures), or `scan_prediction_markets` (prediction) based on UI selection; `cross_ref` passed through for Polymarket reference pricing on prediction scans. Invalid types raise `ValueError` at the boundary. Standalone Polymarket removed from `MARKET_TYPES`, `CATEGORIES_BY_TYPE`, `FILTERS_BY_TYPE`, sidebar `QUICK_SCANS` — UI-only, never reached service layer. CLI `scan.py polymarket` still works. Files: `webapp/services.py`, `webapp/views/scan_page.py`, `webapp/app.py`, `docs/web-app/LOCAL.md`.
- **Q2. Test env-contamination fix.** `test_approved_clean_when_no_caps_hit` read `MAX_BET_SIZE` and `KELLY_FRACTION` from `kalshi_executor` at import time, so a developer `.env` with `MAX_BET_SIZE=15` and `KELLY_FRACTION=1.0` would trip the max-bet cap and return `APPROVED_CAPPED_MAX_BET` instead of `APPROVED`. Fix: monkey-patch both module constants to documented defaults for the test's scope, matching the existing pattern in `test_approved_capped_max_bet`. Files: `tests/test_risk_gates.py`.
- **Q3. Doc drift: count-free "risk gates" references.** `docs/SCRIPTS_REFERENCE.md`, `docs/setup/AUTOMATION_GUIDE.md`, `docs/web-app/LOCAL.md` said "8 risk gates" post-R1/R3. Updated to count-free phrasing ("all risk gates") linking to `CLAUDE.md` §"Execution Gates"; CLAUDE.md heading renamed from "11 Execution Gates" to "Execution Gates". Prevents doc churn on every gate addition.
- **Q4. Pages deploy branch fix.** `.github/workflows/deploy.yml` triggered on `main`; repo default is `master`. Flipped so pushes to master actually redeploy `.claude/html/` (the Edge-Radar data-flow visualization).
- **Q5. Declared `pandas` in `requirements.txt`.** All four `webapp/views/*.py` import pandas; it was working only via Streamlit's transitive dep. Promoted to `pandas>=2.1.4` as a first-class runtime dep.

### R7. Minimum Market-Price Floor (new Gate 3.5)
- **Problem:** F10 from the 2026-04-21 14-day review showed sub-10¢ bets at 1W-3L with the model claiming "+50% edge" on 8-10¢ longshots. One win masked a systemic lottery-ticket overfit pattern.
- **Fix:** New reject gate in `size_order()` — any bet whose market price is below `MIN_MARKET_PRICE` (default **$0.10**) is rejected. Strict less-than: $0.09 rejected, $0.10 approved. No exception for edge/confidence (unlike Gate 4.6's carve-out). Set to 0 to disable and keep all longshots.
- **Defaults:** `MIN_MARKET_PRICE=0.10` chosen in discussion ("I kind of like the long shots. But I definitely agree We shouldn't go too low. I like .10") — blocks the lottery-ticket cluster while keeping moderate longshots (≥10¢) eligible.
- Env: `MIN_MARKET_PRICE` (plumbed through `.env.example`, `CLAUDE.md`, `webapp/services.py` flat-keys for Streamlit Cloud secrets).

### Gate Numbering
- **Total gates:** 12 (was 11). Reject gates 1-7 (including 3.5, 4.5, 4.6); sizing caps 8-9.

### Tests
- 5 new tests for Gate 3.5 (reject below floor, reject just below floor, approve at floor inclusive, approve above floor, disabled when `MIN_MARKET_PRICE=0`). 213 → 218 passing. Two pre-existing tests (`test_contracts_capped_by_bankroll`, `test_price_clamped_to_valid_range`) that intentionally use sub-10¢ prices patched to disable `MIN_MARKET_PRICE` for their scope so they exercise their actual intent.

---

## 2026-04-21 -- 14-Day Review Response (R1, R2, R3, R4)

### 14-Day Review (76 settled trades since 2026-04-07)
- **Sample:** 76 settled, 37W-39L (48.7%), +31% ROI, Brier 0.2646. Aggregate was carried by NHL (+87% ROI) and a single 7¢ MLS outlier.
- **F1 — NO-side systematically loses on high edge:** YES +93% ROI (n=48); NO -20% ROI (n=28); NO at ≥20% edge: 31% WR, -33% ROI (n=16). All 13 high-edge losers in the window were NO-side.
- **F6 — Low confidence:** 0W-3L / -105% ROI, consistent with the 2026-04-18 window.

### R3. `MIN_CONFIDENCE` Reject Gate (new Gate 4.5)
- **Fix:** Reject any opportunity whose confidence label ranks below `MIN_CONFIDENCE` (default `medium`). Low-confidence bets were 0W-3L / -105% ROI across two review windows — rejecting outright instead of warning.
- Env: `MIN_CONFIDENCE` (values: `low` | `medium` | `high`).

### R1. NO-Side Favorite Guard + Half-Kelly Dampener (new Gate 4.6)
- **Problem:** Every high-edge loser in the 14-day window was a NO bet on a heavy favorite. The model over-estimates edge on the "long-price, short-distance" NO side.
- **Fix — reject gate:** Reject NO bets whose market price < `NO_SIDE_FAVORITE_THRESHOLD` (default 0.25) unless edge ≥ `NO_SIDE_MIN_EDGE` (default 0.25) AND confidence = `high`. The carve-out lets genuinely sharp NO plays through but forces the bar much higher than the default 3% floor.
- **Fix — sizing dampener:** NO bets priced below `NO_SIDE_KELLY_PRICE_FLOOR` (default 0.35) are sized at `NO_SIDE_KELLY_MULTIPLIER` (default 0.5 = half-Kelly) of normal Kelly. Complements the reject gate — bets that clear it but are still on moderate favorites get downsized rather than sized at full confidence.
- Env: `NO_SIDE_FAVORITE_THRESHOLD`, `NO_SIDE_MIN_EDGE`, `NO_SIDE_KELLY_PRICE_FLOOR`, `NO_SIDE_KELLY_MULTIPLIER`.

### Gate Numbering
- **Total gates:** 11 (was 9). Reject gates 1-7 (including 4.5 and 4.6); sizing caps 8-9.

### R4. Resting-Order Janitor
- **Problem:** The 14-day review showed 16% of new orders (4/25) resting 25-66h with zero fills. Edge-Radar is fire-and-forget after placing a limit order — nothing polled Kalshi for stale orders. Stranded resting orders tied up balance and cluttered the order book without contributing to P&L.
- **Fix:** New `cancel_stale_resting_orders()` helper in `kalshi_executor.py`. Lists resting orders via `client.get_orders(status="resting")`, filters to those older than `RESTING_ORDER_MAX_HOURS` (default 24) with `fill_count_fp == 0`, and calls `client.cancel_order()` on each. Partial/full fills are left for the settler to handle.
- **Trigger:** Runs at the top of `execute_pipeline()` only when `execute=True` AND `DRY_RUN=false`. Preview scans never touch the order book; dry-run execute calls skip the janitor entirely. With the user's existing 5AM daily `--execute` scan, the natural cadence covers the 24h threshold without needing a separate scheduler.
- Env: `RESTING_ORDER_MAX_HOURS` (0 disables).

### R2. Per-Sport Stdev Bump (supersedes C2)
- **Problem:** Brier 0.2646 (still worse than coin-flip 0.2500) and a 60-70% favorite-band overconfidence gap of +18% (largest bucket, n=40). C1's Kelly soft-cap dampens sizing on fake-high edges but does not touch the underlying probability estimates. The sport-level 14-day numbers (NBA -26%, MLB -10%) persist. Meanwhile NHL is at +87% ROI and well-calibrated.
- **Fix:** Widen the normal-CDF probability distributions for the three underperforming sports.
  - `SPORT_MARGIN_STDEV`: NBA 12.0 -> 13.8 (+15%), NCAAB 11.0 -> 12.1 (+10%), MLB 3.5 -> 4.025 (+15%).
  - `SPORT_TOTAL_STDEV`: NBA 18.0 -> 20.7 (+15%), NCAAB 16.0 -> 17.6 (+10%), MLB 3.0 -> 3.45 (+15%).
  - NHL, NFL, NCAAF, soccer, MMA unchanged.
- **Mechanism:** Wider stdev pulls probability mass toward 50%, directly reducing the favorite-band overconfidence and compressing the implausibly large edges in the >=25% bucket (which realized -24% ROI in the review).
- **Attribution plan:** R12 re-runs `model_calibration.py` at 100 post-baseline trades (currently at 66). The window between R2's ship date and that checkpoint is the cleanest place to measure whether the probability-width fix improved Brier.

### Tests
- 32 new tests (181 -> 213 passing): 6 for `MIN_CONFIDENCE` gate, 4 for NO-side reject gate, 3 for NO-side Kelly multiplier, 12 for the resting-order janitor (stale/young/partial/zero-hours/API-error/malformed-timestamp/default-env coverage), 1 multiplier-vs-full-Kelly comparison, and 6 for the R2 per-sport stdev values (margin + total + NHL-untouched + other-sports-untouched + ticker-prefix lookup).

---

## 2026-04-18 -- Calibration-Driven Risk Tuning & Odds API Rotation Fix

### First Post-Baseline Calibration Run (66 Edge-Radar trades since 2026-04-03)
- **Findings:** Brier score 0.2561 (worse than coin-flip 0.2500); claimed edges >=25% realize -35% ROI while 10-15% claimed edges realize +127%; NBA -15% ROI, NCAAB -62% ROI at the global 3% floor; NHL +100% ROI; same-matchup bets on consecutive days produced compounding losses (LA Angels @ NY Yankees Apr 13/14/15, NY Mets @ LA Dodgers Apr 13/15, Colorado @ Houston Apr 14/15).
- **Report:** `reports/Calibration/2026-04-18_calibration_report.md`.

### C1. Kelly Edge Soft-Cap
- **Problem:** Kelly sizing uses `edge` linearly. A claimed 25% edge sized 2.5x larger than a 10% edge -- and the >=25% bucket is the worst-performing (-35% ROI, 30% WR on 10 trades). The system was sizing biggest on the least-calibrated signal.
- **Fix:** New `trusted_edge()` helper in `kalshi_executor.py` softly caps the edge used inside the Kelly calculation above `KELLY_EDGE_CAP` (default 0.15), with the excess multiplied by `KELLY_EDGE_DECAY` (default 0.5). Example: a claimed 25% edge sizes like 20%, a 35% edge like 25%. Raw edge still flows through gates, reports, rationale, and the trade journal -- only Kelly sizing sees the trusted value.
- Env: `KELLY_EDGE_CAP`, `KELLY_EDGE_DECAY`.

### C3. Per-Sport `MIN_EDGE_THRESHOLD`
- **Problem:** NBA lost -15% ROI (13 post-baseline trades) and NCAAB lost -62% ROI (8 trades in 14-day window) at the 3% global floor, while NHL was +100% on the same floor.
- **Fix:** New `min_edge_for(opp)` helper with `_PER_SPORT_MIN_EDGE` dict populated at import from `MIN_EDGE_THRESHOLD_<SPORT>` env vars (supported: MLB, NBA, NHL, NFL, NCAAB, NCAAF, MLS, SOCCER). Defaults set: `NBA=0.08`, `NCAAB=0.10`. Gate 3 rejection message shows the per-sport floor in effect.

### C5. Series-Level Correlation Dedup (New Gate 7)
- **Problem:** `dedup_correlated_brackets()` deduped within a single day but couldn't see across days. Same-matchup bets on consecutive nights compounded losses (LA Angels @ NY Yankees 3 nights, net negative; NY Mets @ LA Dodgers 2 nights, both losing; COL @ HOU 2 nights, both losing).
- **Fix:** New Gate 7 rejects a new bet if the same matchup (sport + team pair, date-agnostic) was already bet within `SERIES_DEDUP_HOURS` (default 48). `matchup_key(ticker)` strips the leading YY-MMM-DD date and optional HHMM game-time prefix to produce a series-invariant key. `recent_matchups_from_log()` walks the local trade log; dry-run runs don't write to the log, so no extra filtering needed.
- **Gate numbering:** Total gates now 9 (1-7 reject, 8-9 sizing cap). Previously 8.
- Env: `SERIES_DEDUP_HOURS` (0 disables).

### Bug Fix: Odds API Key Rotation Bailed Early
- **Problem:** `scan.py sports --filter mlb` returned 0 MLB events while the all-sports `.bat` scan pulled 28 -- same API keys, same date. With 10 configured keys and the first 3-4 currently exhausted on their monthly quota, the fixed `range(3)` retry loop in `fetch_odds_api()` rotated on each 401 but exited before trying the newly-rotated key. The all-sports scan masked the issue because earlier sports (golf, soccer) rotated past the dead keys first, so by the time MLB was queried the active key was fresh. Single-sport filter runs never got that warmup.
- **Fix:** Replaced the fixed-count loop with a set-based "tried every key at most once" while-loop. Explicit log message when all keys return 401/429 instead of silent empty result. Happy path unchanged (first working key succeeds, no unnecessary rotation). 4 regression tests cover all-keys-tried, rotates-past-exhausted, first-key-success, and single-key-401.
- Files: `scripts/kalshi/edge_detector.py:fetch_odds_api`.

### Tests
- 20 new tests total (161 -> 181 passing): 6 for `trusted_edge`, 5 for per-sport edge floors, 16 for series dedup (`matchup_key`, `recent_matchups_from_log`, gate behavior), 4 for Odds API rotation.

---

## 2026-04-08 -- Full Sports Coverage & Multi-Filter Support

### Expanded Odds API Sport Mapping (4 -> 18 sports)
- **Problem:** `KALSHI_TO_ODDS_SPORT` only mapped 4 sports (NBA, NHL, MLB, NCAAB). All other sports -- NFL, soccer, UFC, boxing, F1, NASCAR, PGA, IPL, college football/women's basketball -- were fetched from Kalshi but silently dropped because no external odds existed to calculate edge against.
- **Fix:** Added mappings for all 14 missing sports with Odds API coverage: NFL (`americanfootball_nfl`), NCAA Football (`americanfootball_ncaaf`), NCAA Women's Basketball (`basketball_wncaab`), MLS (`soccer_usa_mls`), EPL (`soccer_epl`), UCL (`soccer_uefa_champs_league`), La Liga (`soccer_spain_la_liga`), Serie A (`soccer_italy_serie_a`), Bundesliga (`soccer_germany_bundesliga`), Ligue 1 (`soccer_france_ligue_one`), UFC (`mma_mixed_martial_arts`), Boxing (`boxing_boxing`), F1 (`motorsport_formula_one`), PGA (`golf_pga_championship`), IPL (`cricket_ipl`).
- **CATEGORY_MAP expanded:** Added 18 new ticker prefix -> category mappings (NFL game/spread/total, MLS game/spread/total, all soccer leagues, UFC, boxing, IPL, F1, NASCAR, PGA, NCAA women's basketball) so these markets get properly categorized instead of falling to "other".
- **No-filter scan expanded:** Since the unfiltered scan (`scan.py sports`) uses `KALSHI_TO_ODDS_SPORT` keys to determine which prefixes to fetch, this change automatically expands coverage from 11 to 30 prefixes.

### Comma-Separated Multi-Filter (`--filter mlb,nhl`)
- **Problem:** `--filter` only accepted a single sport. Scanning two sports required two separate runs, wasting Odds API quota and time.
- **Fix:** `--filter` now accepts comma-separated values. Each value is resolved independently through `FILTER_SHORTCUTS`, and all prefixes are merged. Example: `--filter mlb,nhl` fetches all MLB and NHL prefixes in one scan.
- **Futures guard:** Single-value futures filters (e.g., `--filter nba-futures`) still route to the dedicated futures scanner as before.
- Files changed: `scripts/kalshi/edge_detector.py`

---

## 2026-04-08 -- Streamlit Community Cloud Deployment

### Web Dashboard Live at edge-radar.streamlit.app
- **Deployed** the Streamlit dashboard to Streamlit Community Cloud (free tier) with password-gated access.
- **Inline PEM support:** `KalshiClient` now accepts private key content as a string (not just a file path), enabling Cloud deployment where no filesystem is available. Priority: inline content > env var > `st.secrets` > file path. Local dev workflow unchanged.
- **Secrets bridge:** `webapp/services.py` injects Streamlit Cloud secrets into `os.environ` before script imports, so all existing `os.getenv()` calls (odds_api, edge_detector, etc.) work on Cloud without modification. Supports both nested (`[kalshi] / api_key`) and flat (`KALSHI_API_KEY`) TOML layouts.
- **Dependency pins loosened:** Changed all `==` pins to `>=` in `requirements.txt` — Streamlit Cloud runs Python 3.14 which can't build `scipy==1.11.4` from source (no Fortran compiler).
- **Repo public-readiness:** Removed tracked `reports/` and `.claude/memory/` from git (were committed before gitignore rules). Added `.claude/memory/` to `.gitignore`.
- **sys.path fix:** Added `webapp/` directory to `sys.path` in `app.py` so bare imports work when Streamlit Cloud runs from the repo root.
- Files changed: `kalshi_client.py`, `webapp/services.py`, `webapp/app.py`, `requirements.txt`, `.gitignore`

---

## 2026-04-06 -- Dynamic Stdev Adjustment (S5 Enhancement)

### S5. Dynamic Stdev Adjustment for Weather
- **Problem:** Sport-specific standard deviations in the normal CDF model were static constants. Weather, rest/B2B, and pitcher signals adjusted confidence or fair value, but only pitcher and rest affected the CDF stdev (and only for totals, not spreads). Spreads had no dynamic stdev adjustment at all.
- **Fix:** Weather now contributes a `stdev_adjustment` alongside its existing fair-value shift. The adjustment scales by severity: severe (+0.5), moderate (+0.3), mild (+0.1), none (0.0). Dome stadiums always return 0.0. Both `detect_edge_spread()` and `detect_edge_total()` now compound all applicable stdev adjustments (weather + rest for spreads; weather + rest + pitcher for totals).
- **Spread improvement:** `consensus_spread_prob()` now accepts a `stdev_adjustment` parameter, bringing spreads to parity with totals. Previously spreads used only the static sport-specific stdev.
- **Caching:** New `_weather_for_market()` cached helper in `scan_all_markets()` fetches weather once per home team, avoiding duplicate NWS API calls across spread and total markets for the same game.
- **Effect:** Bad weather increases the stdev in the normal CDF model, making the system more conservative on alternate lines where uncertainty compounds. Spreads now benefit from the same dynamic stdev pipeline that totals already had.
- Files changed: `scripts/shared/sports_weather.py` (added `stdev_adjustment` to return dict), `scripts/kalshi/edge_detector.py` (`consensus_spread_prob()` accepts stdev_adjustment, `detect_edge_spread()` and `detect_edge_total()` accept weather_data, new `_weather_for_market()` cache helper)

---

## 2026-04-06 -- Code Simplification (S5, S6)

### S5. Deleted `config.py` (Dead Module)
- **Problem:** `scripts/shared/config.py` defined env vars and constants (scoring weights, crypto/weather/SPX constants, `CONFIDENCE_RANK`) that were dead code -- no consumer imported them. The only two live imports were `LOG_DIR` and `LOG_LEVEL` used by `logging_setup.py`.
- **Fix:** Deleted `config.py` entirely. `logging_setup.py` now defines `LOG_DIR` and `LOG_LEVEL` inline (reads from env with `dotenv`). `webapp/services.py` now reads its env vars directly with `os.getenv()` instead of importing from config.
- Files changed: `config.py` (deleted), `logging_setup.py`, `webapp/services.py`

### S6. Removed `MAX_POSITION_CONCENTRATION` Env Var and Risk Gate
- **Problem:** Gate 7 (concentration cap at 20% of bankroll) was redundant with the `MAX_BET_SIZE` hard cap. The hard cap already limits any single position to $100, making a percentage-of-bankroll check unnecessary for the current bankroll range.
- **Fix:** Removed `MAX_CONCENTRATION` variable and concentration gate from `kalshi_executor.py`. Removed `MAX_POSITION_CONCENTRATION` from `.env`, `.env.example`, and `CLAUDE.md`. Removed `APPROVED_CAPPED_CONCENTRATION` approval subtype. Renumbered remaining gates: old gate 8 (max bet size) is now gate 7, old gate 9 (bet ratio cap) is now gate 8.
- **Gate count:** 9 gates reduced to 8. Gates 1-6 reject, gates 7-8 are sizing caps (max bet, bet ratio).
- **Tests:** Concentration gate test removed (101 tests down to 100).
- Files changed: `kalshi_executor.py`, `.env`, `.env.example`, `CLAUDE.md`

---

## 2026-04-06 -- Code Simplification (S3, S4)

### S3. Removed `--max-bet-ratio` and `--max-per-game` CLI Flags
- **Problem:** `--max-bet-ratio` and `--max-per-game` were available as CLI flags, duplicating env-only settings. This added unnecessary complexity to the CLI surface and every scanner's argument parser.
- **Fix:** Removed `--max-bet-ratio` from `edge_detector.py`, `kalshi_executor.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`, and `scan.py` help text. Removed `--max-per-game` from `edge_detector.py` and `kalshi_executor.py`. Removed `max_per_game` and `max_bet_ratio` parameters from `execute_pipeline()` signature.
- **Configuration:** Both settings are now `.env`-only: `MAX_BET_RATIO` (default 3.0) and `MAX_PER_EVENT` (default 2).
- Files changed: `kalshi_executor.py`, `edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`, `scan.py`

### S4. Merged `MAX_BET_SIZE_SPORTS` / `MAX_BET_SIZE_PREDICTION` into Single `MAX_BET_SIZE`
- **Problem:** Two separate env vars (`MAX_BET_SIZE_SPORTS=$50`, `MAX_BET_SIZE_PREDICTION=$100`) required a category lookup helper (`_max_bet_for()`) and a `_SPORTS_CATEGORIES` set in the executor. The distinction added complexity without meaningful risk benefit.
- **Fix:** Unified into a single `MAX_BET_SIZE` env var (default $100). Removed `MAX_BET_SIZE_SPORTS`, `MAX_BET_SIZE_PREDICTION`, `_SPORTS_CATEGORIES` set, and `_max_bet_for()` helper from executor. Risk check dashboard now shows a single "Max Bet Size" row. Gate 8 uses `MAX_BET_SIZE` directly.
- Files changed: `kalshi_executor.py`, `config.py`, `risk_check.py`, `.env.example`

---

## 2026-04-06 -- Code Simplification (S1, S2)

### S1. Removed `DEFAULT_BET_SIZE` (Dead Code)
- `DEFAULT_BET_SIZE` was defined in `kalshi_executor.py` but never referenced anywhere in the codebase. Removed the line. No behavioral change.

### S2. Removed `MIN_CONFIDENCE` Env Var and Risk Gate
- **Problem:** The confidence-floor risk gate (`MIN_CONFIDENCE`) was redundant. Composite score already incorporates confidence as 30% of its weight, so a low-confidence opportunity is already penalized in the score gate. Having a separate confidence gate added complexity without adding safety.
- **Fix:** Removed the `MIN_CONFIDENCE` env var from `kalshi_executor.py`, `config.py`, and `.env.example`. Removed `CONFIDENCE_RANK` dict from executor (kept in `config.py` with a note for scoring use). Removed risk gate 5 (confidence floor). Remaining gates renumbered: old 6-10 become 5-9.
- **Gate count:** 10 gates reduced to 9. Gates 1-4 reject, gates 5-6 reject (duplicate ticker, per-event cap), gates 7-9 are sizing caps (concentration, max bet, bet ratio).
- **Tests:** Confidence gate test removed (102 tests down to 101).
- Files changed: `kalshi_executor.py`, `config.py`, `.env.example`

---

## 2026-04-06 -- Bet Ratio Cap (Risk Gate 10) & Markdown Table Fix

### Risk Gate 10: Bet Ratio Cap (`MAX_BET_RATIO`)
- **Problem:** Kelly sizing could let one high-edge, low-price bet dominate a batch. For example, 41 contracts at $0.21 = $8.61 while two other bets cost ~$2 each. A single outlier absorbs most of the batch budget.
- **Fix:** New `MAX_BET_RATIO` parameter (default 3.0). No single bet can cost more than 3x the median batch cost. Only scales down outliers -- other bets in the batch are untouched.
- **Gate type:** Sizing cap (like gates 8-9). Downsizes the outlier rather than rejecting it. Fires after Kelly sizing and before budget cap.
- **Usage:** Set in `.env` as `MAX_BET_RATIO=3.0` or override per-run with `--max-bet-ratio 2.0`
- **CLI:** `--max-bet-ratio` flag added to all scanners (`edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`) and `scan.py`
- Files changed: `kalshi_executor.py` (new env var, `_apply_bet_ratio_cap()` function, `execute_pipeline()` kwarg, CLI flag), `edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py` (CLI flag + pass-through), `scan.py` (help text), `.env.example`, `CLAUDE.md`

### Markdown Table Pipe Fix
- **Problem:** Report markdown tables had broken column alignment on some rows. `format_bet_label()` in `ticker_display.py` was replacing `" (vs "` with `" | "`, injecting a literal pipe character into markdown table cells -- breaking the table structure.
- **Fix:** Changed replacement from `" | "` to `" vs "` in `ticker_display.py`. Added `.replace("|", "/")` sanitization on bet and pick labels in `report_writer.py` (both scan and execution report writers) as a safety net against future pipe injection.
- Files changed: `ticker_display.py`, `report_writer.py`

---

## 2026-04-06 -- Streamlit Web Dashboard (U6)

### Web Dashboard v1.0
- **Purpose:** Lightweight web UI for occasional remote access. CLI remains primary interface.
- **Stack:** Streamlit with custom dark theme (JetBrains Mono + Outfit fonts, cyan/amber/red accent palette)
- **Pages:**
  - **Scan & Execute** — all CLI flags as controls, scan to find opportunities, preview to see sizing/costs, execute to place orders
  - **Portfolio** — balance, open positions, P&L, daily loss limit progress, resting orders
  - **Settle & Report** — settle completed markets, generate P&L reports rendered as formatted markdown
- **Architecture:** Thin service layer (`webapp/services.py`) wraps existing scanner/executor/settler functions. Captures `rich` console output via stdout redirect. No business logic duplication.
- **Theme:** Custom CSS injection (`webapp/theme.py`) — dark terminal aesthetic with grid overlay, styled metric cards, gradient buttons
- **Auth:** Optional password gate via `.streamlit/secrets.toml` (gitignored)
- **Code changes:** `kalshi_settler.py` `generate_report()` now returns markdown string for web rendering
- **Skill:** Official `streamlit/agent-skills` installed at `.claude/skills/developing-with-streamlit/` (17 sub-skills)
- **Docs:** `docs/web-app/` — SETUP.md, USAGE.md, ARCHITECTURE.md
- Launch: `streamlit run webapp/app.py`

### Dashboard Enhancements (D1, D2, D4 + polish)
- **D1: Quick-scan sidebar buttons** — Sports, Futures, Prediction, Polymarket buttons in sidebar pre-select market type
- **D2: Favorite scans** — Save/load/delete named scan configs. Stored in `data/webapp/favorites.json`. Favorites appear in sidebar for one-click loading.
- **D4: Default unit size** — Changed from $1.00 to $0.50
- **Dynamic controls** — Filter, category, budget, max-per-game, and cross-ref controls adapt based on selected market type. Sports-only params hidden for futures/prediction/polymarket.
- **Clear button** — Wipes all scan results, preview, and execution data for a fresh start
- **ANSI stripping** — Console output cleaned of escape codes and rich markup before display
- **Rich table removal** — Preview shows clean pipeline summary + Streamlit dataframe instead of box-drawing character tables
- **Expander replacement** — All `st.expander` widgets replaced with toggle buttons (Material icon font renders as broken text in the custom theme)

---

## 2026-04-06 -- Min-Bets Safety Gate

### `--min-bets` Flag
- **Problem:** With `--budget 10%` and `--max-bets 6`, if only 1-2 games pass risk checks, the entire budget gets concentrated into too few positions — defeating the purpose of diversification.
- **Fix:** New `--min-bets N` flag across all scanners. If fewer than N opportunities pass the 9 risk gates, the pipeline aborts before execution with a clear message.
- **How it works:** Gate fires after risk checks but before sizing/budget scaling. Returns an empty list so no orders are placed and no reports are generated for an under-diversified batch.
- **No flag = no minimum:** When `--min-bets` is omitted (default `None`), the gate is skipped entirely — current behavior unchanged.
- Example: `scan.py sports --unit-size .5 --max-bets 6 --min-bets 3 --budget 10% --exclude-open --execute`
- Files changed: `kalshi_executor.py` (new gate in `execute_pipeline`), `edge_detector.py`, `prediction_scanner.py`, `polymarket_edge.py`, `futures_edge.py` (CLI flag + pass-through in all four)

---

## 2026-04-04 (evening) -- Budget Cap for Batch Execution

### `--budget` Flag
- **Problem:** No way to control total batch cost. Kelly + unit sizing determines per-bet amounts independently, but there was no ceiling on the sum. Users wanting to limit daily exposure to a fixed percentage of bankroll (e.g., 10%) had no mechanism to enforce it.
- **Fix:** New `--budget` flag on `scan.py`, `edge_detector.py`, and `kalshi_executor.py`. Accepts a percentage of bankroll (e.g., `10%`) or a flat dollar amount (e.g., `15`).
- **How it works:** After all bets are sized normally (Kelly/flat, per-bet caps), if total cost exceeds the budget, all approved bets are proportionally scaled down. Higher-edge bets keep proportionally more capital (Kelly weighting preserved). Each bet keeps at least 1 contract, so the actual total may slightly undershoot the budget due to contract rounding.
- **No budget = no change:** When `--budget` is omitted, the pipeline behaves exactly as before. When total is already under the budget, a green confirmation message is shown and no scaling occurs.
- Example: `scan.py sports --unit-size .5 --max-bets 5 --budget 10% --date today --exclude-open`
- Files changed: `kalshi_executor.py` (new `_apply_budget_cap()`, `budget` param on `execute_pipeline`, CLI flag), `edge_detector.py` (CLI flag + pass-through), `scan.py` (help text)

---

## 2026-04-04 (afternoon) -- Fill-Based Accounting, Sizing Gate Docs, Pitcher Parallelization

### X5. Fill-Based Trade Logging
- **Problem:** The executor logged `contracts` and `cost_dollars` from the *requested* order, not from the Kalshi API fill response. Resting or partially-filled orders overstated exposure, distorted P&L, and corrupted settlement math.
- **Fix:** `log_trade()` now records both requested and filled values:
  - `requested_contracts` / `requested_cost` — what we asked for
  - `filled_contracts` / `filled_cost` — what Kalshi actually executed (primary accounting fields)
  - `fill_status` — `resting` | `partial` | `filled`
  - Legacy `contracts` / `cost_dollars` now reflect filled values for backward compatibility
- New `get_filled_contracts()` and `get_filled_cost()` helpers in `trade_log.py` with backward-compatible fallback for pre-X5 trade records
- `kalshi_settler.py` — `calculate_pnl()` uses filled values; resting orders (zero fills) skipped during settlement; settlement log and reconciliation use filled contracts
- `risk_check.py` — "Total wagered" in P&L summary and dashboard uses filled cost
- Execution output now flags resting and partial fills visually: `(RESTING — no fills yet)`, `(PARTIAL — 3/10 filled)`
- **16 new regression tests** covering: fill helpers (old/new format), fully filled, partial fill, zero fill/resting, settlement P&L with fill-based cost

### X6. Sizing Caps vs Reject Gates (Docs + Code)
- **Problem:** `ARCHITECTURE.md` described gates 8 (concentration) and 9 (max bet) as reject gates, but the executor silently downsized and approved. Post-trade review couldn't tell if an order passed cleanly or was force-capped.
- **Fix (docs):** `ARCHITECTURE.md` now correctly documents gates 1-7 as reject gates and gates 8-9 as sizing caps with "Cap — downsize to..." behavior
- **Fix (code):** `size_order()` returns approval subtypes:
  - `APPROVED` — clean pass, no caps hit
  - `APPROVED_CAPPED_CONCENTRATION` — downsized by gate 8
  - `APPROVED_CAPPED_MAX_BET` — downsized by gate 9
- All downstream pipeline filtering updated to use `.startswith("APPROVED")`
- **3 new tests** for clean approval, concentration cap, and max bet cap scenarios

### Pitcher Stats Parallelization
- `prefetch_mlb_pitchers()` now uses `ThreadPoolExecutor(max_workers=8)` to fetch all pitcher stats concurrently
- MLB scan time reduced from ~60s to ~35s (pitcher fetch specifically: ~60s → ~11s)
- Single-game `get_game_pitchers()` also parallelized (2 pitchers fetched concurrently)

### Batch-Aware Kelly Sizing
- **Problem:** Kelly sizing was applied independently per bet, so placing 10 simultaneous bets could commit 10x what single-bet Kelly intends. Total batch exposure could exceed 50% of bankroll.
- **Fix:** `size_order()` now accepts a `batch_size` parameter. Kelly fraction is divided by the number of bets in the batch: `effective_kelly = KELLY_FRACTION / batch_size`. Each bet gets its proportional share, keeping total batch exposure consistent with what single-bet Kelly would allocate.
- `execute_pipeline()` passes `min(len(opportunities), max_bets)` as the batch size
- `KELLY_FRACTION` is now configurable in `.env` (was only in `.env.example` before)

### Bug Fix: Pitcher Data NoneType Error
- Fixed `AttributeError: 'NoneType' object has no attribute 'get'` when MLB Stats API returns `None` for a pitcher (TBD starters)
- Changed `pitcher_data.get("away_pitcher", {}).get(...)` to `(pitcher_data.get("away_pitcher") or {}).get(...)` in both game and totals detection paths

### Test Suite
- **102 tests** (up from 83): +16 fill accounting, +3 approval subtypes

---

## 2026-04-04 -- Per-Game Diversification, Pitcher Data, Rest Days, Calibration

### Correlated Bracket Dedup & Per-Game Cap Reduction
- **Problem:** Automated execution was stacking 3 of 5 bets on the same game (e.g., Over 221.5, Over 224.5, Over 228.5 on BOS@MIL). These are highly correlated — they win or lose together.
- **Fix 1:** New `dedup_correlated_brackets()` in `kalshi_executor.py` — groups opportunities by `(event_key, category)` and keeps only the highest composite score from each group. Multiple totals lines on the same game collapse to the single best one.
- **Fix 2:** `MAX_PER_EVENT` default lowered from 3 to 2 (allows ML + totals on the same game, but not 3 correlated lines)
- **Fix 3:** Scanner-level `_cap_per_game` in `edge_detector.py` also lowered from 3 to 2
- New `--max-per-game N` CLI flag on both `edge_detector.py` and `kalshi_executor.py` for session-level override
- `size_order()` accepts `max_per_event` parameter instead of using the global directly

### S1. MLB Starting Pitcher Data (`scripts/shared/pitcher_stats.py`)
- New module fetching probable pitchers + season stats from MLB Stats API (free, no key)
- **Stats fetched:** ERA, FIP (approximated), WHIP, K/9, innings pitched, record, days rest
- **Pitcher tiers:** ace (ERA ≤ 3.20), mid (ERA ≤ 4.50), back (ERA > 4.50 or TBD)
- **Matchup classification** with stdev adjustments to the total probability model:
  - ace vs ace: -0.3 stdev (tighter game, lean under)
  - ace vs mid: -0.15 stdev (lean under)
  - mid vs mid: no adjustment (neutral)
  - mid vs back: +0.2 stdev (lean over)
  - bullpen day: +0.5 stdev (high variance, lean over)
- **Integration in `edge_detector.py`:**
  - Pre-fetches all pitcher data per game date in `scan_all_markets()` (step 3c)
  - Totals: stdev adjusted by matchup quality, confidence bumped/dropped by pitcher signal
  - Games: pitcher info attached to details (informational — moneyline odds already price in starters)
  - `consensus_total_prob()` now accepts `stdev_adjustment` parameter
- **`prefetch_mlb_pitchers(date)`** — bulk pre-fetch for all games on a date, indexed by team abbreviation
- CLI: `python scripts/shared/pitcher_stats.py 2026-04-04` for a quick pitcher table

### S2. NBA/NHL Back-to-Back & Rest Day Detection (`scripts/shared/rest_days.py`)
- New module detecting back-to-backs and rest days via ESPN scoreboard API (free, no key)
- Checks 1-4 days back per team to calculate days since last game
- **NBA adjustments:** B2B adds +1.5 to stdev (more variance/fatigue), leans under. Well-rested (3+ days) tightens stdev by -0.5
- **NHL adjustments:** B2B adds +0.3 stdev, slight under lean
- Returns per team: `is_b2b`, `days_rest`, `opponent_is_b2b`, `rest_advantage`, `stdev_adjustment`, `confidence_signal`
- **Integration in `edge_detector.py`:**
  - Pre-fetches rest data for NBA/NHL in `scan_all_markets()` (step 3d)
  - Totals: stdev adjusted by rest situation, confidence bumped for under when B2B
  - Games/Spreads: confidence adjusted based on rest advantage (B2B team less likely to win/cover)
  - Rest info attached to opportunity details for transparency
- Auto-routes through `scan.py` — no extra flags needed
- CLI: `python scripts/shared/rest_days.py basketball_nba 2026-04-04` for a quick rest table

### W2. Model Calibration Tool (`scripts/kalshi/model_calibration.py`)
- New script analyzing settled trades to surface calibration issues and generate prioritized recommendations
- **Reports:** Overall Brier score, calibration curve (predicted vs realized by probability bucket), dimension breakdowns (category, confidence, sport, edge bucket), confidence x category cross-tab
- **Recommendations engine:** Prioritized HIGH/MEDIUM/LOW actions for stdev adjustments, confidence signal fixes, edge estimation issues
- **Parked until post-baseline data:** Calibration baseline set to 2026-04-03 — pre-baseline trades span multiple model versions and produce misleading recommendations. Re-run after 100+ post-baseline trades.
- CLI: `python scripts/kalshi/model_calibration.py --save --days 30`

### X4. Startup Doctor (previously implemented, marked DONE in roadmap)
- `scripts/doctor.py` verified functional — checks Python version, venv, credentials, data dirs, config, API connectivity, pre-commit hooks
- Fixed stale `MAX_PER_EVENT` default (3 → 2) in doctor display

---

## 2026-04-02 -- Execution Correctness, Risk Gates, Kelly Sizing, Display Overhaul

### X1. Portable Python Path
- `scan.py` now uses `sys.executable` instead of hardcoded `.venv/Scripts/python.exe`
- Works across any environment (CI, WSL, Docker, other machines)

### X2. Nine Risk Gates Enforced in Executor
- **Previously:** `kalshi_executor.py` loaded `KELLY_FRACTION`, `MAX_CONCENTRATION`, and `MAX_BET_SIZE` but never enforced them. Only 5 of 9 gates were active.
- **Now:** All 9 gates enforced before every order: daily loss, position count, edge, score, confidence, duplicate ticker, per-event cap, max concentration, max bet size
- **Kelly sizing:** Quarter-Kelly with flat unit as floor. High-edge bets get more contracts; low-edge bets stay at minimum unit size
- **Category-aware bet caps:** Sports ($50) vs prediction ($100) separate limits
- **Batch tracking:** Approved orders update the open ticker set and event counts in-flight so gates apply correctly across the run
- New env vars: `MAX_PER_EVENT=3`, `MAX_POSITION_CONCENTRATION=0.20`

### X3. Per-Event Position Caps (built into X2)
- Max 3 positions per game/event (configurable via `MAX_PER_EVENT`)
- Extracts event key from ticker (strips pick suffix) to group markets by game
- Prevents hidden concentration where 7 of 10 positions are on the same matchup

### D1. Bet Type Column
- Added Type column (ML/Spread/Total/Prop) to all 7 output tables across scan, execute, positions, and settlement views
- New `bet_type_from_ticker()` helper in `ticker_display.py`

### D2. Descriptive Pick Column
- Replaced raw YES/NO Side column with descriptive Pick: "Spurs win", "Over 220.5", "Blazers -7.5"
- New `format_pick_label()` helper in `ticker_display.py`
- Added Kalshi team abbreviation aliases (SAS, GSW, NOP, etc.)

### D3. Sport Column
- Added Sport column (NBA/NHL/MLB/NFL/NCAAB/etc.) to scan table, executor preview table, and markdown reports
- New `sport_from_ticker()` helper in `ticker_display.py`
- Added `KXNCAABB` prefix alias for NCAA basketball championship tickers

### D4. Context-Aware Report Saving
- When `--unit-size` is passed, saves an **execution report** (Sport, Bet, Type, Pick, Qty, Price, Cost, Edge, total cost) instead of the scan report
- When no `--unit-size`, saves the scan report as before (Mkt, Fair, Edge, Conf, Score)
- New `save_execution_report()` function in `report_writer.py`
- `execute_pipeline` now returns sized orders on preview (was returning `[]`) so the report writer can use them

### Same-Day Automated Execution Scripts
- New `scripts/schedulers/same_day_executions/same_day_scan.bat` — preview all sports today, top 10 across all sports
- New `scripts/schedulers/same_day_executions/same_day_execute.bat` — scan + execute, with portfolio status before/after
- Recommended run time: 8 AM ET (all markets posted, sportsbook lines sharp, Kalshi lag window open)
- Single command scans NFL, NBA, NHL, MLB together, ranked by composite score, 10 bets max total
- Next-day scripts also available at `scripts/schedulers/next_day_executions/` as reserve

### How Scoring Works (ARCHITECTURE.md)
- New section explaining the full flow: Fair Value → Edge → Confidence → Score
- Includes dependency diagram, confidence thresholds by market type, composite score formula with weights, and worked example

### Documentation Overhaul
- `docs/scripts/` subdirectory: 7 dedicated script docs (edge_detector, futures_edge, prediction_scanner, polymarket_edge, kalshi_executor, kalshi_settler, risk_check)
- `SCRIPTS_REFERENCE.md` slimmed to hub with routing table, common flags, daily workflow
- `kalshi_executor.py` reframed as Portfolio Status + Execution Library; `run` subcommand deprecated
- `scan.py` flags table added (13 flags documented)
- All 25 prompts updated + 6 new prompts added (totals-only, spreads-only, multi-sport-execute, weekly-review, risk-audit, full-prediction-execute)
- ARCHITECTURE.md, CLAUDE.md, README.md, SKILL.md, .env.example all updated with 9-gate risk model
- ROADMAP.md restructured with 6 tiers, informed by 3rd-party assessment

---

## 2026-03-31 -- Unified Scanner, Scheduler Reorganization, Env & Report Cleanup

### P9. Unified Scan Entry Point (`scripts/scan.py`)
- Single entry point routing to all 4 scanners: `sports`, `futures`, `prediction`, `polymarket`
- Auto-inserts `scan` subcommand when omitted
- Aliases: `sport`, `pred`, `poly`, `xref`
- All flags forwarded directly via subprocess — no duplicate argument parsing
- Updated Quick Start, More Examples, Daily Workflow, and Scripts Reference to use `scan.py`

### P10. Documentation Cleanup
- Updated SPORTS_GUIDE: replaced all `kalshi_executor.py run` with `scan.py sports`, removed duplicated daily workflow (defers to SCRIPTS_REFERENCE), fixed composite score dimensions (3 → 4 with weights), added roadmap cross-link
- Updated FUTURES_GUIDE and PREDICTION_MARKETS_GUIDE: `scan.py` commands, roadmap cross-links
- Updated ARCHITECTURE: replaced duplicated Phase 2-4 task lists with pointer to ROADMAP.md
- Added back-links from SCRIPTS_REFERENCE to all domain guides

### P11. Pre-Commit Hooks (`.pre-commit-config.yaml`)
- `detect-secrets` — credential leak prevention (requires `.secrets.baseline`)
- `black` — code formatting (line-length 100)
- `flake8` — linting (max-line-length 100, ignore E203/W503)
- `check-json`, `check-yaml` — config file validation
- `end-of-file-fixer`, `trailing-whitespace` — whitespace hygiene
- `no-commit-to-branch` — prevents direct commits to master
- Install: `make hooks` or `pip install pre-commit && pre-commit install`

### P12. Makefile
- 18 targets: `scan-mlb`, `scan-nba`, `scan-nhl`, `scan-nfl`, `scan-sports`, `scan-futures`, `scan-predictions`, `scan-polymarket`, `scan-all`, `status`, `risk`, `settle`, `report`, `reconcile`, `test`, `test-quick`, `install`, `hooks`
- `make help` for full reference
- Note: requires `make` installed (`choco install make` on Windows)

### Scheduler Directory Reorganization
- Moved 4 `.bat` morning scan jobs to `scripts/schedulers/morning_scans/`
- Moved 2 Python automation scripts to `scripts/schedulers/automation/`
- Fixed `PROJECT_ROOT` depth in `install_windows_task.py` for new path
- Updated all path references in CLAUDE.md, README.md, SCRIPTS_REFERENCE.md

### P7. `MAX_BET_SIZE_SPORTS` Added to `.env.example`
- Added `MAX_BET_SIZE_SPORTS=50` — was referenced in CLAUDE.md and used by `risk_check.py` but missing from the env template

### P8. Report Output Format Unified
- Confirmed all scanners support `--save` for markdown reports
- `kalshi_executor.py run` delegates scanning to dedicated scanners (which have `--save`), so no gap remains
- Marked complete in roadmap

---

## 2026-03-30 -- Unified CLI, Readable Displays, Date Filtering, Project Cleanup

### Unified CLI Flags Across All Scanners
- All 4 scanners (`edge_detector.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`) now share the same execution flags: `--execute`, `--unit-size`, `--max-bets`, `--pick`, `--ticker`, `--save`
- Previously `--execute`/`--unit-size`/`--max-bets` only worked on `edge_detector.py` and `futures_edge.py`; prediction and polymarket scanners required routing through `kalshi_executor.py`

### Date & Open Position Filters
- Added `--date` flag to all scanners and executor: filter opportunities by game date
  - Accepts: `today`, `tomorrow`, `YYYY-MM-DD`, `MM-DD`, `mar31`
- Added `--exclude-open` flag: automatically skips markets where you already have an open position (both sides of the same game)
- Both filters work on all 5 entry points

### Shared Ticker Display Module (`scripts/shared/ticker_display.py`)
- New shared module for parsing Kalshi tickers into human-readable labels
- `parse_game_datetime()` -- extracts "Mar 30 6:40pm" from any ticker
- `parse_matchup()` -- extracts "White Sox @ Miami" from game tickers
- `parse_pick_team()` -- extracts picked team name from ticker suffix
- `format_bet_label()` -- best-effort readable label for any market type
- Team name lookups for MLB (30), NBA (30), NHL (32 teams)
- All 8 display tables across 7 scripts now show game date/time and readable matchup names

### Live Risk Dashboard (`scripts/kalshi/risk_check.py`)
- Rewritten to pull live data from Kalshi API (was reading empty local JSON files)
- Shows: account balance, risk limits, open positions with readable names + dates, resting orders, today's P&L, watchlist
- Positions table shows "Bet | When | Pick | Qty | Cost | P&L" instead of raw tickers

### Executor Status Improvements (`scripts/kalshi/kalshi_executor.py`)
- `status` command now shows readable matchups + game dates instead of raw tickers

### Markdown Report Format (`scripts/kalshi/kalshi_settler.py`)
- `report --detail --save` now generates proper markdown (tables, headers, bold values, code-formatted tickers)
- Changed file extension from `.txt` to `.md`

### MLB Filtering Guide (`docs/kalshi-sports-betting/MLB_FILTERING_GUIDE.md`)
- New comprehensive guide covering 10 filtering categories for MLB picks
- Includes composite strategies: "Strong MLB Play", "Weather Fade", "Sharp Follow", "Regression Fade", "Early Season Value"

### Markdown Scan Reports (`scripts/shared/report_writer.py`)
- New shared module: all scanners now save a markdown report alongside the JSON watchlist when `--save` is passed
- Reports include: readable matchups, game dates, edge/fair/market prices, confidence, composite score
- Saved to `reports/Sports/`, `reports/Futures/`, `reports/Predictions/` with date-stamped filenames
- Example: `reports/Sports/2026-03-30_mlb_sports_scan.md`

### Test Suite (83 tests)
- Created `tests/` with 4 test files covering the highest-value targets
- `test_risk_gates.py` (19 tests): position sizing (`unit_size_contracts`), all 5 risk gate rejections, bankroll capping, price clamping
- `test_ticker_display.py` (30 tests): team code splitting, date/time parsing, matchup rendering, date filtering, position exclusion
- `test_edge_detection.py` (14 tests): N-way de-vigging, normal CDF spread/total probability math
- `test_weather.py` (11 tests): MLB and NFL weather threshold adjustments, severity classification
- Shared fixtures in `conftest.py` for sample Opportunity objects

### Standardized Logging
- All 8 entry-point scripts migrated from `logging.basicConfig` + `logging.getLogger` to `setup_logging()` from `scripts/shared/logging_setup.py`
- Every script now gets console output (INFO+) plus a dedicated log file in `logs/` (DEBUG+)
- Zero `logging.basicConfig` calls remain in the codebase
- Library modules (`team_stats.py`, `line_movement.py`, etc.) correctly use `logging.getLogger()` to inherit config from entry points

### Consolidated Import Boilerplate
- Created `.venv/Lib/site-packages/edge_radar.pth` — auto-adds all script directories to `sys.path` when the venv is active
- Removed 16 `sys.path.insert(0, ...)` lines across 15 files
- Scripts now directly import shared modules without path setup boilerplate
- Created `scripts/bootstrap.py` as fallback for non-venv usage

### Removed Scheduler Framework
- Deleted `base_scheduler.py`, `sports_scheduler.py`, `prediction_scheduler.py`, `run_schedulers.py`, `scheduler_config.py`
- The framework was overengineered — every scheduler just called `scan_all_markets()` → `execute_pipeline()`, which the CLI scripts already do
- Replaced with direct Windows Task Scheduler / cron scheduling using the existing scanner scripts
- Kept `daily_sports_scan.py` (morning edge report) and `install_windows_task.py` (Task Scheduler helper)
- Removed `docs/schedulers/SCHEDULER_GUIDE.md`
- Added "Scheduling Your Own Scans" section to SCRIPTS_REFERENCE with `schtasks` examples

### Save Flag for Status & Risk Commands
- `kalshi_executor.py status --save` saves portfolio status as markdown to `reports/Accounts/Kalshi/kalshi_status_YYYY-MM-DD.md`
- `risk_check.py --save` saves full risk dashboard as markdown to `reports/Accounts/Kalshi/kalshi_dashboard_YYYY-MM-DD.md`
- Reports include: account balance, open positions (readable matchups + dates), today's P&L, resting orders, watchlist

### Project Cleanup
- Removed empty `strategies/` directory (edge detection is centralized in scanners, not strategy-pattern architecture)
- Updated CLAUDE.md project structure to reflect current state (`tests/`, `ticker_display.py`, `report_writer.py`)

---

## 2026-03-28 -- Polymarket Cross-Reference Integration

### Polymarket Edge Module (`scripts/polymarket/polymarket_edge.py`)
- New module: cross-references Kalshi market prices against Polymarket via the Gamma API (free, no key required)
- Fetches active Polymarket markets by category (crypto, weather, S&P, politics, companies)
- Fuzzy market matching engine using 4 signals: title similarity, strike price, expiry date, asset keyword overlap
- Standalone edge detection: surfaces price discrepancies between Kalshi and Polymarket as arbitrage-style signals
- Enrichment mode: boosts composite score when Polymarket confirms an existing edge, penalizes when it disagrees
- Standalone CLI: `polymarket_edge.py scan`, `polymarket_edge.py match TICKER`

### Prediction Scanner Integration (`scripts/prediction/prediction_scanner.py`)
- Added `--cross-ref` flag to enable Polymarket cross-referencing during scans
- Added `--filter polymarket` / `poly` / `xref` shortcuts (auto-enables cross-ref mode)
- When active, the scanner: (1) finds standalone cross-market edge opportunities, and (2) enriches all existing opportunities with Polymarket confirmation/disagreement signals
- New `cross_ref` parameter on `scan_prediction_markets()` for programmatic use

---

## 2026-03-23 -- Edge Model Overhaul, Scheduler Framework, Doc Consolidation

### Spread & Total Model Recalibration (`scripts/kalshi/edge_detector.py`)
- Replaced linear probability adjustment (`+3% per point`) with normal CDF model using `scipy.stats.norm`
- Infers expected score margin from book spread + implied probability, then calculates P(margin > strike) on the bell curve
- Added sport-specific standard deviations: NBA (12), NCAAB (11), NFL (13.5), MLB (3.5), NHL (2.5), soccer (1.8)
- Same fix applied to total (over/under) markets with separate total stdev values
- Old model systematically overestimated edge on alternate spreads (caused 1W-11L on NCAAB)

### Daily Morning Scan (`scripts/schedulers/daily_sports_scan.py`)
- New script: scans MLB, NBA, NHL, NFL each morning for top 25 opportunities
- Saves timestamped report to `reports/Sports/daily_edge_reports/YYYY-MM-DD_morning_scan.md`
- Report includes edge, fair value, market price, confidence, team stats, sharp signals, weather
- `--daemon` flag runs via APScheduler at 8:00 AM PST daily with automatic DST handling
- `--top N` to customize number of opportunities (default 25)

### Line Movement & Sharp Money Detection (`scripts/shared/line_movement.py`)
- New module: ESPN scoreboard API provides opening vs closing odds (DraftKings) for free
- Detects reverse line movement (spread moves away from favorite = sharp on underdog)
- Detects sharp total movement (total drops/rises >2 pts)
- Pre-fetched once per scan, integrated into game/spread/total confidence signals
- Sharp agreement boosts confidence; contradiction reduces it
- Covers NBA, NFL, NHL, MLB, NCAAB, NCAAF

### Weather Impact for Outdoor Sports (`scripts/shared/sports_weather.py`)
- New module: NWS hourly forecast for 31 NFL + 30 MLB venues (dome/outdoor classified)
- Scoring adjustment model: wind >15mph, rain >40%, cold <32F (NFL) / <45F (MLB)
- Integrated into `detect_edge_total()`: bad weather reduces over fair value, boosts under
- Dome stadiums automatically skipped (zero adjustment)
- Free NWS API, no key required

### Team Stats Integrated into Edge Detection (`scripts/kalshi/edge_detector.py`)
- Game and spread edge detectors now look up team win% via `team_stats.py`
- Stats signal: "supports" (win% >= 60% for YES, <= 40% for NO), "contradicts" (opposite), or "neutral"
- Confidence is bumped up one level when stats support the bet, dropped when stats contradict
- Team record and signal stored in opportunity details for transparency

### Sharp Book Weighting (`scripts/kalshi/edge_detector.py`, `scripts/kalshi/futures_edge.py`)
- Added `BOOK_WEIGHTS` map: Pinnacle/Circa at 3x, mid-tier at 1-1.5x, DraftKings/FanDuel/BetMGM at 0.7x
- Replaced simple median with `weighted_median()` across all consensus functions (game, spread, total, futures)
- Sharp books pull the consensus fair value toward their more accurate lines
- 21 books mapped with weights; unknown books default to 1.0x

### Team Stats Module (`scripts/shared/team_stats.py`)
- New module providing team performance data from free APIs (no keys required)
- ESPN API: NBA, NCAAB, NFL, NCAAF standings, win%, points for/against
- NHL Stats API: standings, goal differential, L10 record, streak
- MLB Stats API: standings, run differential, winning percentage
- 6 sports covered, unified `get_team_stats(team, sport)` lookup with fuzzy name matching
- Data cached per session to minimize API calls

### Closing Line Value Tracking (`scripts/kalshi/kalshi_settler.py`)
- Settler now captures closing price from Kalshi API when settling trades
- Calculates CLV = closing_price - entry_price per trade
- Performance report includes CLV section: average CLV and beat-the-close rate
- CLV is the gold standard for validating whether the model has real predictive value

### Rebranded to Edge-Radar
- Renamed from FinAgent / Finance-Agent-Pro / edge-hunter to Edge-Radar
- Updated all references across CLAUDE.md, README, ARCHITECTURE, agents, Python docstrings, User-Agent headers, reports, and memory

### Documentation Consolidation
- Merged `USER_GUIDE.md` + `BETTING_GUIDE.md` into single `SPORTS_GUIDE.md` (1117 → 405 lines)
- Replaced `KALSHI_STRATEGY_PLAN.md` with lean `ARCHITECTURE.md` (pipeline, risk gates, data flow)
- Trimmed `FUTURES_GUIDE.md` (456 → 359 lines) and `PREDICTION_MARKETS_GUIDE.md` (414 → 252 lines)
- Slimmed `README.md` (206 → 79 lines) with doc index linking to all guides
- Eliminated ~600 lines of duplicated risk gates, command examples, and filter tables across docs

---

## 2026-03-23 -- Scheduler Framework, Trade Log Cleanup, Report Export

### Scheduler Framework (`scripts/schedulers/`)
- New per-market scheduler architecture — each sport/market gets its own independent scheduler
- `BaseScheduler` class with DRY_RUN enforcement, consecutive failure auto-pause (5 strikes), structured logging
- `SportsScheduler` and `PredictionScheduler` subclasses calling existing pipelines directly (no subprocess wrapping)
- `scheduler_config.py` — profiles loaded from `SCHED_{NAME}_*` env vars (9 registered: NBA, NHL, MLB, NFL, NCAA, soccer, crypto, weather, SPX)
- `run_schedulers.py` — CLI entry point: `--list` (show all profiles), `--only nba` (single), or launch all enabled in parallel
- All schedulers disabled by default — enable via `SCHED_{NAME}_ENABLED=true` in `.env`
- Docs: `docs/schedulers/SCHEDULER_GUIDE.md`

### Trade Log Cleanup
- Cross-validated local trade log against Kalshi API fills — identified 32 demo trades mixed with 12 live trades
- Purged all demo trades from `kalshi_trades.json` and `kalshi_settlements.json`
- Backups saved: `kalshi_trades_pre_cleanup_2026-03-23.json`, `kalshi_settlements_pre_cleanup_2026-03-23.json`
- Report now shows accurate live-only data: 12 trades, $10.67 wagered

### Report File Export
- Added `--save` flag to `kalshi_settler.py report` — writes plain-text report to `reports/Accounts/Kalshi/kalshi_report_YYYY-MM-DD.txt`
- Report includes timestamp, strips Rich markup for clean text output

### Kalshi Client Hardening
- Changed default `KALSHI_BASE_URL` fallback from demo API to production API
- Prevents accidental demo connection if env var is unset

### Odds API Key Expansion
- Added 2 additional Odds API keys (3 total) for increased rate limit capacity
- Existing key rotation in `odds_api.py` handles this automatically

### Memory System
- Added `.claude/memory/` for cross-session project context
- CLAUDE.md updated to instruct Claude Code to check memory on startup

### Futures Betting Improvements (`scripts/kalshi/futures_edge.py`)
- Added `KXNBA` (NBA Finals Champion), `KXNHL` (Stanley Cup Champion), `KXMLB` (World Series Champion) to futures map — only conference/playoff markets were previously mapped
- Added human-readable labels to all futures: output now shows "NBA Finals Champion: Oklahoma City Thunder" instead of just the ticker
- `--filter nba-futures` now scans Finals champion + both conference winners
- `--filter nfl-futures` cleaned up (removed KXNFLMVP which has no Odds API data)
- Bet type label stored in `details["bet_type"]` and used as the display title
- CLI table shows "Bet Type" column instead of raw ticker
- Updated FUTURES_GUIDE.md with NBA Finals section and corrected filter descriptions

### Per-Game Opportunity Cap (`scripts/kalshi/edge_detector.py`)
- Limits scan results to top 3 opportunities per game (sorted by edge)
- Groups markets by date+matchup extracted from ticker (e.g., all spreads/totals/game for Michigan vs Alabama share one key)
- Prevents a single game from dominating the opportunity list

### PR #14 Review
- Reviewed and rejected Jules-generated PR "Automate Kalshi Betting Pipeline & Optimize Execution"
- Issues: missing `KELLY_FRACTION` constant (runtime crash), no `DRY_RUN` gate on scheduler, missing `apscheduler` dependency, unexplained `cryptography` addition
- Built proper scheduler framework as replacement (see above)

---

## 2026-03-22 -- Live Trading, Prediction Markets, Project Reorganization

### Switched to Live Trading
- Moved from Kalshi demo to live production API
- Set `DRY_RUN=false`, `MAX_BET_SIZE_PREDICTION=5`
- Demo credentials archived in `.env` comments

### Git Repository
- Published to GitHub as private repo: `michaelschecht/Edge-Radar`
- Working branch: `mike_desktop`

### Kalshi Bettor Agent & Skill
- New `.claude/agents/KALSHI_BETTOR.md` -- dedicated Kalshi betting agent
- New `.claude/skills/kalshi-bet/SKILL.md` -- `/kalshi-bet` slash command for scan/execute/settle
- Agent auto-runs status on startup, previews before executing, respects all risk gates

### Financial Analysis Skill
- New `.claude/skills/financial-analysis/` -- research and analysis skill
- Templates: stock analysis, earnings/corporate, global markets, market sentiment, investment strategy

### Futures / Championship Edge Detector (`scripts/kalshi/futures_edge.py`)
- N-way de-vigging of outright odds from 5-12 sportsbooks
- Fuzzy name matching between Kalshi candidates and Odds API outcomes with alias table
- Supported: NFL Super Bowl, NBA conference winners, NHL conference winners, MLB playoffs, NCAAB MOP, PGA golf
- Filter shortcuts: `futures`, `nba-futures`, `nhl-futures`, `mlb-futures`, `ncaab-futures`, `golf-futures`, `nfl-futures`
- Integrated routing from `edge_detector.py` -- `--filter nba-futures` auto-routes to futures scanner
- Browse-only: NBA/NHL awards, Heisman, soccer leagues, F1, NASCAR, IPL

### Unfiltered Scan Fix
- Running the scanner without `--filter` now scans all known sport prefixes instead of pulling 5000 generic multi-event markets
- Results: 959+ sport markets across NBA, NCAAB, MLB, NHL instead of 0

### Sport Filter Expansion
- Expanded `FILTER_SHORTCUTS` from 5 to 27 sports based on live Kalshi market discovery
- Added: NFL, NCAA women's basketball, NCAA football, MLS, Champions League, EPL, La Liga, Serie A, Bundesliga, Ligue 1, UFC, boxing, F1, NASCAR, PGA golf, IPL cricket, individual esports (CS2, LoL)
- Added NBA player props (3PT, rebounds, assists, steals, points) and awards (MVP, ROY, DPOY)
- Added NHL awards (Hart, Norris, Calder)

### Prediction Market Edge Detectors (`scripts/prediction/`)
- **`probability.py`** -- shared math: strike probability (log-normal model), weather probability (normal model), realized volatility
- **`crypto_edge.py`** -- BTC, ETH, XRP, DOGE, SOL edge detection via CoinGecko (free API, with rate limit retry)
- **`weather_edge.py`** -- NYC, Chicago, Miami, Denver temperature markets via NWS API (free, no key). Uncertainty scales with forecast horizon.
- **`spx_edge.py`** -- S&P 500 binary options using Yahoo Finance for price + VIX for implied volatility
- **`mentions_edge.py`** -- TV mention markets: Poisson model for KXLASTWORDCOUNT (word counts), historical YES rate for binary mention markets (KXPOLITICSMENTION, KXFOXNEWSMENTION, KXNBAMENTION)
- **`companies_edge.py`** -- KXBANKRUPTCY (normal distribution vs historical ~750/yr baseline), KXIPO (browse only)
- **`politics_edge.py`** -- KXIMPEACH, KXQUANTUM, KXFUSION: time-decay hazard model with calibrated annual probabilities
- **`prediction_scanner.py`** -- unified CLI scanner with filters: crypto, weather, spx, mentions, companies, politics, techscience, and individual asset/series shortcuts
- All detectors produce the same `Opportunity` dataclass compatible with the existing executor pipeline

### Project Reorganization
- **Scripts:** Moved all Kalshi scripts to `scripts/kalshi/`, new prediction scripts in `scripts/prediction/`
- **Docs:** Reorganized into `docs/kalshi-sports-betting/` and `docs/kalshi-prediction-betting/`
- Fixed all `parent.parent` path resolution for new script depth
- Updated all cross-references across CLAUDE.md, agents, skills, and docs
- Removed local filesystem paths from all committed files

### Architecture Optimization
- **`scripts/shared/opportunity.py`** -- single Opportunity dataclass (was duplicated in edge_detector + prediction_scanner)
- **`scripts/shared/trade_log.py`** -- centralized trade log I/O (was duplicated in executor, settler, edge_detector)
- **`scripts/shared/paths.py`** -- standardized path setup replacing ad-hoc sys.path hacks
- **`scripts/shared/config.py`** -- centralized config: risk limits, scoring weights, model params, all loaded from .env
- **`scripts/shared/logging_setup.py`** -- dual logging to console (INFO+) and daily log file (DEBUG+) in `logs/`
- **`--prediction` flag on executor** -- prediction scanner now feeds directly into the execution pipeline
- **`reconcile` command on settler** -- compares local trade log vs Kalshi API positions, flags discrepancies
- **CLAUDE.md** updated to reflect actual implementation status vs planned features
- **`.env.example`** updated with all actually-used variables

### Odds API Key Rotation (`scripts/shared/odds_api.py`)
- Supports multiple API keys via `ODDS_API_KEYS=key1,key2,key3` in `.env`
- Auto-rotates to next key on 401/429 (exhausted/rate limited)
- Tracks remaining requests per key from response headers
- Warns when a key drops below 10 remaining
- Backwards compatible with single key

### Prompt Library (`prompts/`)
- 18 ready-to-use prompts for agents across 3 categories:
  - `prompts/sports-betting/` (6): daily scan, sport-specific, execute, settle, high conviction, compare
  - `prompts/futures/` (5): championship scan, sport report, weekly tracker, best value, portfolio builder
  - `prompts/predictions/` (7): all predictions, crypto, weather, SPX, mentions, execute, morning brief

### Reports
- `reports/NFL/2026-03-22_superbowl_futures.md` -- Super Bowl analysis (KC NO +1.6% best edge)
- `reports/mlb/2026-03-22_mlb_playoff_futures.md` -- MLB playoffs (Cleveland YES +25.5%, Cincinnati YES +21.0%)
- `reports/NBA/2026-03-22_nba_championship_futures.md` -- NBA championship (OKC YES +26.3% biggest edge across all sports)

### README
- Complete rewrite focused on sports betting, futures, and prediction markets
- Project structure, quick start, all market categories, API reference
- Removed financial-analysis skill (project dedicated to betting)

### Repo Renamed
- `Finance-Agent-Pro` -> `edge-hunter` -> `Edge-Radar`

### New Skills
- `market-mechanics-betting` -- betting theory, Kelly criterion, scoring rules
- `polymarket` -- API reference, trading guides, getting started docs

### Documentation
- `docs/kalshi-sports-betting/BETTING_GUIDE.md` -- comprehensive sport-by-sport guide with all 27 filters
- `docs/kalshi-prediction-betting/PREDICTION_MARKETS_GUIDE.md` -- crypto, weather, S&P 500, mentions, companies, politics, tech/science
- `docs/kalshi-futures-betting/FUTURES_GUIDE.md` -- NFL, NBA, NHL, MLB, golf futures with N-way de-vig
- Updated KALSHI_BETTOR agent and kalshi-bet skill with futures + prediction commands
- Updated all docs to reflect live trading, new script paths, and new commands

---

## 2026-03-18 (Session 2) -- Settlement Tracker, Filters, Unit Sizing

### Settlement Tracker (`scripts/kalshi/kalshi_settler.py`)
- Polls Kalshi settlements API and matches results to trade log
- Falls back to checking individual market status if settlement not yet posted
- Calculates per-trade P&L: revenue, cost, fees, net P&L, ROI, win/loss
- Updates trade log records with `closed_at`, `net_pnl`, `settlement_result`, `settlement_won`
- Saves settlement history to `data/history/kalshi_settlements.json`
- Performance report with: win rate, profit factor, ROI, best/worst trades
- Edge calibration: estimated edge vs. realized edge, realization rate
- Breakdowns by confidence level and market category
- `--detail` flag for per-trade table

### Sport Filtering (`--filter`)
- Added `--filter` flag to both `edge_detector.py scan` and `kalshi_executor.py run`
- Named shortcuts: `ncaamb`, `nba`, `nhl`, `mlb`, `esports`
- Also accepts raw Kalshi ticker prefixes (e.g. `KXHIGHNY`, `KXINX`)
- Only fetches odds for the filtered sport, saving Odds API quota
- Added `KXNCAAMBGAME` to category map and odds sport mapping

### Fixed Unit Sizing
- Replaced Kelly criterion with fixed unit sizing
- Default unit size: $1.00 (configurable via `UNIT_SIZE` in `.env`)
- Contracts = round($unit / price), always at least 1
- Override per run with `--unit-size` flag
- Examples: $0.02 price -> 50 contracts, $0.50 price -> 2 contracts

### Kalshi Client Update
- Added `get_settlements()` method for settlement history endpoint

### Documentation
- `docs/kalshi-sports-betting/USER_GUIDE.md` -- Complete usage guide with filtering and unit sizing sections
- Updated all docs to reflect settlement tracker, filters, and unit sizing

---

## 2026-03-18 (Session 1) -- MVP Pipeline Complete

### Kalshi API Client (`scripts/kalshi/kalshi_client.py`)
- Built authenticated API client with RSA-PSS request signing
- Supports: get_markets, get_market, get_all_open_markets, get_balance, get_positions, get_fills, create_order, cancel_order, get_order, get_orders
- CLI for quick testing (balance, markets, positions, orders, market detail)
- DRY_RUN safety gate blocks live orders on non-demo environments
- Auto-resolves relative key paths from project root
- Tested against demo env -- all endpoints confirmed working

### Edge Detector (`scripts/kalshi/edge_detector.py`)
- Scans 5000+ open Kalshi markets via paginated API calls
- Categorizes markets by ticker prefix: game, spread, total, player_prop, esports, mention, other
- Integrates with The Odds API for sportsbook consensus pricing
- Three edge models implemented:
  - **Game outcomes:** De-vigs h2h odds from 8-12 books, takes median as fair value
  - **Spreads:** Adjusts book spread probability for Kalshi strike difference
  - **Totals:** Adjusts book total probability for Kalshi line difference
- Fuzzy team name matching between Kalshi and Odds API (alias table + substring matching)
- Composite scoring: 40% edge strength, 30% confidence, 20% liquidity, 10% time sensitivity
- CLI: `scan` (batch scan) and `detail` (single market deep dive)
- Saves scored opportunities to `data/watchlists/kalshi_opportunities.json`

### Automated Executor (`scripts/kalshi/kalshi_executor.py`)
- Full scan-to-execution pipeline in one command
- Risk management gates before every order:
  - Daily loss limit check
  - Max open positions check
  - Minimum edge threshold
  - Minimum composite score
  - Confidence level filter
- Quarter-Kelly position sizing with concentration caps
- Executes limit orders on Kalshi, logs all trades
- Trade logging to `data/history/kalshi_trades.json` with full context (edge, fair value, Kelly fraction, fees)
- Portfolio status dashboard: balance, positions, P&L, resting orders, daily activity
- CLI: `run` (preview or execute), `status` (dashboard)

### First Live Demo Execution
- Placed 6 orders on Kalshi demo (1 manual test + 5 automated)
- 5 filled immediately, 1 resting
- Portfolio: $38.44 balance, $59.72 portfolio value, 5 open positions
- Total wagered: $74.09 across NBA games, spreads, MLB

### Configuration & Setup
- Demo API keys configured in `keys/demo/`
- Production API keys stored in `keys/live/`
- `.env` configured for demo environment
- `ODDS_API_KEY` added for The Odds API (free tier, 500 req/month)
- Added `keys/`, `*.key`, `*.pem` to `.gitignore`

### Documentation
- `docs/kalshi-sports-betting/KALSHI_STRATEGY_PLAN.md` -- System overview, pipeline description, remaining work
- `docs/kalshi-sports-betting/KALSHI_API_REFERENCE.md` -- API endpoints, auth, rate limits, CLI reference
- `docs/CHANGELOG.md` -- This file

---

## Pre-2026-03-18 -- Project Foundation

### Existing Before This Session
- `CLAUDE.md` -- Master project manifest with risk limits, agent roster, execution chain
- `.claude/agents/` -- 5 agent specs (MARKET_RESEARCHER, TRADE_EXECUTOR, RISK_MANAGER, DATA_ANALYST, PORTFOLIO_MONITOR)
- `scripts/kalshi/fetch_odds.py` -- The Odds API integration for sports value betting
- `scripts/kalshi/fetch_market_data.py` -- Multi-asset data fetcher (stocks, prediction markets, crypto)
- `scripts/kalshi/risk_check.py` -- Portfolio risk dashboard
- `scripts/sql/init_db.sql` -- Database schema (8 tables, 2 views)
- `.env.example` -- Environment variable template
- `.gitignore` -- Configured for Python, data files, credentials
- `.venv` -- Python virtual environment with dependencies
