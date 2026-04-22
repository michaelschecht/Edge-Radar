# Script & Configuration Simplification

*Created: 2026-04-06*
*Tracked in: ROADMAP.md as H5*

After incrementally adding risk gates, env vars, and CLI flags over two weeks, the system has accumulated complexity that can be reduced without losing functionality. This document lists concrete simplifications, rationale, and implementation notes.

---

## S1. Remove `DEFAULT_BET_SIZE` (dead code)

**Current state:** `kalshi_executor.py:57` reads `DEFAULT_BET_SIZE` from `.env` but nothing references the variable anywhere in the codebase.

**Action:** Delete the line. No other changes needed.

**Risk:** None — confirmed unused via grep.

---

## S2. Remove `MIN_CONFIDENCE` env var and risk gate

**Current state:** Two quality filters gate every bet independently:
- `MIN_COMPOSITE_SCORE` (default 6.0) — composite of edge, confidence, liquidity, time
- `MIN_CONFIDENCE` (default `medium`) — standalone confidence floor

The composite score already incorporates confidence as 30% of its weight (`CONFIDENCE_WEIGHT=0.3` in `config.py`). In practice, a `low` confidence bet almost never reaches a 6.0 composite score because confidence drags the composite down. The two gates are redundant.

**Action:**
1. Remove `MIN_CONFIDENCE` from `kalshi_executor.py`, `.env.example`, `config.py`, `CLAUDE.md`
2. Remove risk gate 5 (confidence floor) from `size_order()`
3. Update gate numbering in docs (10 gates → 9 gates)
4. The composite score continues to penalize low-confidence bets — no behavioral change

**Risk:** Low. If a low-confidence bet somehow scores 6.0+ composite, it has enough edge and liquidity to justify execution. The composite score is the better holistic filter.

---

## S3. Remove `--max-bet-ratio` and `--max-per-game` CLI flags (keep as `.env` only)

**Current state:** These two flags were added as CLI overrides for env vars, but they're "set once and forget" parameters — not things you'd vary between runs. Every other run uses `--unit-size`, `--max-bets`, `--budget`, `--date`, and `--filter`, which genuinely change per invocation.

**Flags to remove from CLI (6 files):**
- `--max-bet-ratio` — added to `edge_detector.py`, `kalshi_executor.py`, `futures_edge.py`, `prediction_scanner.py`, `polymarket_edge.py`, `scan.py`
- `--max-per-game` — in `edge_detector.py`, `kalshi_executor.py`

**Action:**
1. Remove `add_argument("--max-bet-ratio", ...)` from all 5 scanner/executor scripts
2. Remove `add_argument("--max-per-game", ...)` from `edge_detector.py` and `kalshi_executor.py`
3. Remove passthrough kwargs (`max_bet_ratio=args.max_bet_ratio`, `max_per_game=args.max_per_game`) from all `execute_pipeline()` calls
4. Remove `max_bet_ratio` parameter from `execute_pipeline()` signature — always use env var
5. Remove `max_per_game` parameter from `execute_pipeline()` — always use `MAX_PER_EVENT` env var
6. Update `scan.py` help text
7. Keep both env vars in `.env.example` — they still work, just not per-run

**Risk:** If a future workflow needs a per-run override, the flag can be re-added. The env var is always available.

---

## S4. Merge `MAX_BET_SIZE_SPORTS` / `MAX_BET_SIZE_PREDICTION` into single `MAX_BET_SIZE`

**Current state:** Two env vars with different defaults ($50 sports, $100 prediction). The split exists because prediction markets "often have longer time horizons and more data sources." In practice, the user sets both and rarely changes them independently.

**Action:**
1. Replace both with `MAX_BET_SIZE` (default $50)
2. Remove `_max_bet_for()` helper and `_SPORTS_CATEGORIES` set from `kalshi_executor.py`
3. Update `.env.example`, `config.py`, `CLAUDE.md`

**Risk:** Medium. If you want different caps for sports vs prediction, this removes that. Could keep both and just document that most users only need one. **Decision: ask Michael — if he currently runs the same cap for both, merge. If different, leave as-is.**

---

## S5. Pick a direction on `config.py`

**Current state:** `config.py` defines all env vars with defaults, but `kalshi_executor.py` (the file that actually uses them) reads `os.getenv()` directly with its own defaults. Both files exist, neither is authoritative. The `config.py` note even says: *"Some scripts still read os.getenv() directly for historical reasons."*

**Options:**
- **Option A: Delete `config.py`** — `kalshi_executor.py` is the real source of truth since it's where the gates run. Other scripts that need a value import it from the executor. Simplest.
- **Option B: Migrate to `config.py`** — Make `kalshi_executor.py` import from `config.py` instead of reading env vars directly. Single source of defaults, validated at startup. More correct, but more churn.

**Recommendation:** Option A (delete). The executor already works correctly. `config.py` adds a second place to maintain defaults with no consumer. The prediction model constants (crypto vol, weather uncertainty) that live in `config.py` can move to their respective scanner files where they're actually used.

**Risk:** Low for Option A. Option B is lower risk but more work.

---

## S6. Remove `MAX_POSITION_CONCENTRATION` or lower the default

**Current state:** Gate 8 caps any single position at 20% of bankroll. With `MAX_BET_SIZE_SPORTS=50` and a typical bankroll of $500+, a single bet maxes out at 10% concentration. The 20% gate never fires.

**Options:**
- **Remove entirely** — the max bet size cap already prevents oversized bets
- **Lower to 10%** — matches the actual effective cap, but then it's identical to the max bet size gate and still redundant
- **Keep at 20%** — it's a safety net for edge cases (bankroll drops below $250)

**Recommendation:** Keep it but acknowledge it's a backstop, not an active gate. No code change needed — just awareness that it's effectively a no-op at normal bankroll levels. If bankroll grows significantly and bet sizes scale up, this gate becomes relevant again.

---

## Summary

| # | Change | Env vars removed | CLI flags removed | Risk |
|---|--------|-----------------|-------------------|------|
| S1 | Remove `DEFAULT_BET_SIZE` | 1 | 0 | None | **DONE** |
| S2 | Remove `MIN_CONFIDENCE` | 1 | 0 | Low | **DONE** |
| S3 | Remove `--max-bet-ratio`, `--max-per-game` flags | 0 | 2 (×6 files) | Low | **DONE** |
| S4 | Merge bet size caps | 1 | 0 | Medium | **DONE** |
| S5 | Delete `config.py` | 0 | 0 | Low | **DONE** |
| S6 | Remove `MAX_POSITION_CONCENTRATION` | 1 | 0 | Low | **DONE** |

**Net reduction (S1-S3, S5):** 2 env vars, 2 CLI flags, 1 dead file, 1 risk gate. No behavioral change.

S4 requires a decision on whether sports and prediction bet caps are ever set differently.
