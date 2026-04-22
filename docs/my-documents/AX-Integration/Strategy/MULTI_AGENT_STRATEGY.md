# Multi-Agent Collaboration Strategy for Edge-Radar on AX Platform

*Revised: 2026-04-18 — collapsed from 7-agent to 3-agent roster*

---

## Executive Summary

Edge-Radar's workflow decomposes cleanly into three lifecycle phases — **pre-trade, trade, post-trade**. This document specifies a **3-agent AX Platform configuration** where each agent owns one phase. This is a deliberate simplification of the earlier 7-agent draft: fewer handoffs, fewer coordination failures, and a clean mapping onto Edge-Radar's existing `scan -> risk-check -> size -> execute -> settle` pipeline.

The adversarial validation value of a separate analyst agent is preserved **inside** the Hunter (two independent methods, one agent). Real-time monitoring is folded into the Auditor's phase alongside calibration. Execution is deterministic (9 gates + Kalshi API), so the Gatekeeper is a single clean boundary rather than two coordinating agents.

---

## Current Architecture (Single-Agent)

```
[Fetch] -> [Categorize] -> [Compare] -> [Cap] -> [Risk-Check] -> [Execute] -> [Monitor]
```

A single Claude Code session runs the entire pipeline sequentially, with no second opinion, no real-time monitoring between manual check-ins, and no automated calibration loop from settled trades back to the scanner.

**Key bottlenecks:**
1. Edge detection uses a single model — if it is wrong, no backstop
2. Scanning is sequential — sports, then futures, then predictions, one at a time
3. No real-time monitoring of open positions between manual check-ins
4. News and sentiment are not factored in (injury reports, lineup changes, weather updates)
5. No feedback loop where post-settlement results inform the next scan cycle

---

## Proposed Multi-Agent Architecture on AX

### Agent Roster

| Agent | Handle | Phase | Absorbs | Spec |
|:------|:-------|:------|:--------|:-----|
| **Edge-Hunter** | `@edge_hunter` | Pre-trade | Scanner + Arbiter + Analyst | [Agents/EDGE_HUNTER.md](Agents/EDGE_HUNTER.md) |
| **Edge-Gatekeeper** | `@edge_gatekeeper` | Trade | Risk Gate + Executor | [Agents/EDGE_GATEKEEPER.md](Agents/EDGE_GATEKEEPER.md) |
| **Edge-Auditor** | `@edge_auditor` | Post-trade | Sentinel + Auditor | [Agents/EDGE_AUDITOR.md](Agents/EDGE_AUDITOR.md) |
| **Edge-Radar-Scriptor** | `@edge_radar_scriptor` | Cross-cutting (coordinator, not in trade path) | — | [Agents/COORDINATOR.md](Agents/COORDINATOR.md) |

### Data Flow

```
            ┌─────────────────────────────────────────────────┐
            │                 Edge-Hunter                      │
            │  scan -> cross-ref -> validate (2 methods)       │
            └──────────────────┬───────────────────────────────┘
                               │  OPPORTUNITY (validated only)
                               v
            ┌─────────────────────────────────────────────────┐
            │               Edge-Gatekeeper                    │
            │  9 gates -> Kelly size -> place order            │
            └──────────────────┬───────────────────────────────┘
                               │  EXECUTED + watch:<ticker>
                               v
            ┌─────────────────────────────────────────────────┐
            │                Edge-Auditor                      │
            │  monitor -> settle -> calibrate -> feedback      │
            └──────────────────┬───────────────────────────────┘
                               │  CALIBRATION UPDATE
                               └──────> back to Edge-Hunter
                               │  ALERT (urgent)
                               └──────> back to Edge-Gatekeeper
```

### Why 3, Not 7

| Rationale | Explanation |
|:----------|:------------|
| Clean lifecycle boundary | Each phase has a single owner; no ambiguous "who does this" cases |
| Lower coordination overhead | This is a single-user system — 7 agents is coordination theater, not value |
| Preserves adversarial validation | Hunter runs two methods internally; the value-add of the old `@edge_analyst` is retained without a separate agent |
| Execution stays deterministic | Gatekeeper is code-driven (9 gates, Kelly, RSA-signed Kalshi). No benefit to splitting |
| Calibration is natively post-trade | The old Auditor + Sentinel were both post-trade; merging is more natural than splitting |
| Fewer agents = fewer failure modes | Each additional agent is another message contract, another availability dependency |

**What we give up:** vendor-diverse validation as a separate step (the old "Claude scanner vs. GPT-4 analyst" pattern). This can be restored later by running Hunter's second method on a different model — still one agent, heterogeneous internally.

---

## Collaboration Patterns

Three patterns, one per message type. Each maps to one phase transition.

### Pattern 1: Validated Opportunity Handoff (Hunter -> Gatekeeper)

**Problem:** Scanner output goes directly to execution without challenge, and historical data shows overestimation (e.g., NCAAB spread debacle: estimated 33% edge, realized -88% ROI).

**Solution:** Hunter never forwards an opportunity that has not cleared a second-method check. Only validated opportunities reach the Gatekeeper.

```
Hunter: scan -> method1 -> method2 -> agree? -> OPPORTUNITY -> Gatekeeper
                                    -> disagree -> log to scan:rejected:{date}
```

Method pairings are defined in [Agents/EDGE_HUNTER.md](Agents/EDGE_HUNTER.md) (ELO vs de-vig for sports, Monte Carlo vs CDF for spreads, etc.).

**AX tools:** `messages` (send OPPORTUNITY), `context` (scan:*, prices:*), `tasks` (research deep-dives).

---

### Pattern 2: Real-Time Position Alerts (Auditor -> Gatekeeper)

**Problem:** Between execution and settlement, conditions change — injuries, weather shifts, line movement, breaking news. No agent is watching.

**Solution:** Auditor polls `watch:*` keys, monitors external feeds, and on trigger sends an urgent ALERT to Gatekeeper with a recommendation (close/reduce/hold).

```
Auditor: poll watch:* -> check feeds -> trigger? -> ALERT(urgency=high) -> Gatekeeper
                                                 -> Gatekeeper decides: close/reduce/hold
```

Example trigger: star player ruled OUT after bet placed -> urgent ALERT -> Gatekeeper places close order.

**AX tools:** `messages` (urgent priority), `context` (alert:*, watch:*), `search`.

---

### Pattern 3: Calibration Feedback Loop (Auditor -> Hunter)

**Problem:** Without a feedback loop, model drift goes undetected. The scanner keeps using the same methodology even when settled data shows systematic bias.

**Solution:** After every settlement batch, the Auditor buckets bets by edge range and computes realized ROI per bucket. Detected bias is published as `calibration:{model}` context and sent as a CALIBRATION UPDATE message to Hunter. Hunter applies the adjustment factor on the next scan.

```
Auditor: settle -> bucket by edge -> detect bias -> calibration:{model} -> CALIBRATION UPDATE -> Hunter
                                                 -> Hunter adjusts future edge estimates
```

Baseline captured 2026-04-03. First calibration run 2026-04-18 showed Brier 0.2561 with the high-edge bucket inverted — empirical proof that this loop is necessary, not theoretical.

**AX tools:** `messages`, `context` (calibration:*, settlement:*), `tasks` (improvement items).

---

## AX Context Schema

Standardized keys for inter-agent data sharing. Each key has a single writer to avoid race conditions.

| Key Pattern | Contents | TTL | Writer | Readers |
|:------------|:---------|:----|:-------|:--------|
| `scan:{type}:{date}` | Validated opportunity list | 24h | Hunter | Gatekeeper |
| `scan:rejected:{date}` | Opportunities that failed validation | 7d | Hunter | Auditor |
| `prices:{ticker}` | Multi-source price matrix | 1h | Hunter | Gatekeeper, Auditor |
| `risk:daily_pnl` | Today's P&L running total | 24h | Gatekeeper | All |
| `risk:open_count` | Number of open positions | 1h | Gatekeeper | All |
| `watch:{ticker}` | Open position watch data | Until settled | Gatekeeper | Auditor |
| `alert:{ticker}:{type}` | Active alert (injury, weather, etc.) | 4h | Auditor | Gatekeeper |
| `calibration:{model}` | Model bias + adjustment factor | 30d | Auditor | Hunter |
| `settlement:{date}` | Daily settlement summary | 30d | Auditor | Hunter |

---

## Message Protocols

### OPPORTUNITY (Hunter -> Gatekeeper)

```
OPPORTUNITY: Lakers vs Celtics - LAL moneyline
TICKER: KXNBAGAME-31MAR26LALBOS-LAL
EDGE: 7.2% | FAIR: $0.43 | ASK: $0.36
CONFIDENCE: high | SCORE: 8.1
SOURCES: 11 books, sharp agreement, team stats confirm
VALIDATION: pass - Method1=7.2%, Method2=5.8%
CROSS_REF: Polymarket agrees (YES at $0.45)
CALIBRATION_ADJUST: x0.95 (NBA ML slight over-estimate)
ACTION: request_approval
```

### EXECUTED (Gatekeeper -> Auditor)

```
EXECUTED: KXNBAGAME-31MAR26LALBOS-LAL
SIZE: 3 contracts @ $0.36 = $1.08
GATES: 9/9 passed
DAILY_PNL: -$2.30 (limit: -$250)
OPEN: 4 of 10
KELLY: edge=7.2%, fraction=0.25, size_raw=$1.44, size_capped=$1.08
ORDER_ID: 7f3a2b1c-...
WATCH_KEY: watch:KXNBAGAME-31MAR26LALBOS-LAL
```

### REJECTED (Gatekeeper -> Hunter)

```
REJECTED: KXNBAGAME-31MAR26LALBOS-LAL
GATES_FAILED: [3, 5]
REASON: Edge below per-sport threshold (5.8% vs 8% NBA min); already holding KXNBAGAME-31MAR26LALBOS-BOS
DAILY_PNL: -$2.30
OPEN: 4 of 10
```

### ALERT (Auditor -> Gatekeeper)

```
ALERT: POSITION AT RISK
TICKER: KXNBAGAME-31MAR26LALBOS-LAL
TRIGGER: LeBron James ruled OUT (ESPN, 3:42 PM)
SOURCE: ESPN @ 2026-03-31T15:42:00-04:00
IMPACT: fair value $0.43 -> $0.31
RECOMMENDATION: close
URGENCY: high
```

### CALIBRATION UPDATE (Auditor -> Hunter)

```
CALIBRATION UPDATE
MODEL: ncaab_spread
BIAS: +5.3% (scanner over-estimates)
N: 47
ADJUSTMENT: multiply scanner edge by 0.85
CONFIDENCE: medium (n=47, 60-day window)
EFFECTIVE: 2026-04-18
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1-2)

| Task | Details |
|:-----|:--------|
| Register 3 agents on AX | `whoami(action='update')` for each with bio, specialization, capabilities |
| Establish handles | `@edge_hunter`, `@edge_gatekeeper`, `@edge_auditor` |
| Context namespace setup | Declare writer/reader per key (see schema above) |
| Message protocol smoke test | Hunter posts OPPORTUNITY -> Gatekeeper responds -> Auditor receives EXECUTED |

### Phase 2: Gatekeeper Live (Week 3)

Wire Gatekeeper to the existing `scripts/scan.py --execute` pipeline. The 9 gates already work; this phase is about making the execution path observable via AX messages rather than local-only logs.

| Task | Details |
|:-----|:--------|
| AX message emission in executor | On every order placement, post EXECUTED to `@edge_auditor` |
| Populate watch:* on execution | Gatekeeper writes `watch:<ticker>` with entry price, edge, triggers |
| DRY_RUN parity | Ensure dry-run emits same message flow for testing |

### Phase 3: Hunter Validation (Week 4-5)

Implement the two-method validation inside Hunter.

| Task | Details |
|:-----|:--------|
| Per-market counter-method | ELO, Monte Carlo, options skew, ensemble weather |
| Agreement threshold | Both methods must confirm edge >= MIN_EDGE_THRESHOLD |
| Disagreement logging | `scan:rejected:{date}` with both estimates |
| Calibration adjustment | Apply `calibration:{model}` factor before publishing edge |

### Phase 4: Auditor Monitoring + Feedback (Week 6-8)

The highest-value phase. Closes the feedback loop that the original pipeline lacked.

| Task | Details |
|:-----|:--------|
| Live monitoring feeds | ESPN injuries, NWS updates, sportsbook line movement |
| Auto-populate watch list | From `watch:*` keys set by Gatekeeper |
| Urgent alert emission | ALERT messages with `urgency: high` on triggers |
| Settlement pickup | After `kalshi_settler.py settle`, Auditor auto-runs calibration |
| Calibration cron | Monthly full recalibration; weekly bias check; daily bucket update |
| CLV analysis | Rolling 30-day CLV per sport; escalate to Michael if negative |

### Phase 5: Research Deep-Dives (Week 9+)

For markets without a quantitative model (Fed rate, political events, IPOs), Hunter spawns a research task and synthesizes findings from multiple data sources internally (CME FedWatch, Polymarket, PredictIt, Manifold).

| Task | Details |
|:-----|:--------|
| Research task templates | Fed rate, political, IPO, commodities |
| Multi-source synthesis | Hunter aggregates findings in one task |
| Human-in-the-loop | CONFIDENCE=medium + `human_review=true` flag for high-stakes |

---

## Expected Impact

| Metric | Current (Single Agent) | Projected (3-Agent) | Why |
|:-------|:-----------------------|:--------------------|:----|
| False positive rate | ~40% (from settlement data) | ~20% | Hunter's two-method validation filters overestimated edge |
| Scan coverage | Sequential | Parallel within Hunter | Hunter runs scan types concurrently in one agent |
| Reaction to news | Manual (next user check) | Minutes | Auditor's live monitoring |
| Model drift detection | Manual (periodic review) | Automatic | Auditor's calibration loop, triggered on every settlement batch |
| Cross-market signal | Polymarket only (when `--cross-ref`) | 3-5 sources always | Hunter's cross-reference is mandatory, not optional |
| Edge accuracy | Single model estimate | Two independent methods must agree | Hunter's adversarial validation |
| Coordination overhead | N/A | Low (3 agents, 3 message types) | Deliberate simplification vs 7-agent design |

---

## Open Questions

1. **Agent hosting** — All three as Claude Code MCP connections, or Auditor as a persistent cloud agent (for continuous monitoring without keeping a session open)?
2. **Latency vs. validation cost** — For crypto and same-day sports, does the two-method validation step add unacceptable delay? Possible escape hatch: auto-approve below a size threshold.
3. **Vendor diversity inside Hunter** — Worth running Hunter's second method on a different model (e.g., GPT-4) to preserve heterogeneous validation?
4. **Human approval threshold** — Should Michael remain in the loop for all executions, or only above a dollar threshold (e.g., > $10/bet)?
5. **Monthly calibration cron** — Still pending as of 2026-04-18. What's the host — Windows Task Scheduler, GitHub Action, or AX scheduled trigger?

---

## Migration From 7-Agent Draft

The earlier draft proposed seven agents: Scanner, Analyst, Sentinel, Arbiter, Risk Gate, Executor, Auditor. Mapping to the new roster:

| Old Agent | New Home | Notes |
|:----------|:---------|:------|
| Scanner | Edge-Hunter | Primary method inside Hunter |
| Arbiter | Edge-Hunter | Cross-ref step inside Hunter |
| Analyst | Edge-Hunter | Counter-method (validation) inside Hunter |
| Risk Gate | Edge-Gatekeeper | The 9 gates |
| Executor | Edge-Gatekeeper | Kalshi order placement |
| Sentinel | Edge-Auditor | Live monitoring folded into post-trade agent |
| Auditor | Edge-Auditor | Calibration + settlement processing |

The existing `.claude/agents/` files (`MARKET_RESEARCHER.md`, `DATA_ANALYST.md`, `RISK_MANAGER.md`, `TRADE_EXECUTOR.md`, `PORTFOLIO_MONITOR.md`) predate this strategy and can be retired or collapsed into the three new specs once the AX agents are live.
