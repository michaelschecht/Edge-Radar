# Edge-Radar Web App Recommendations

Date: 2026-04-04
Source reviewed: `D:\AI_Agents\Specialized_Agents\Edge_Radar`

## Bottom Line

Yes. `Edge_Radar` can be turned into a working web app, and the strongest path is to treat the current project as a proven decision engine plus exchange connector, then build a real application layer around it.

The current codebase is not a web app foundation yet. It is a script-first trading system with useful reusable logic:

- market scanning and edge detection
- risk gates and position sizing
- Kalshi authentication and order placement
- portfolio/status/reporting flows
- some regression coverage around high-risk money logic

The right move is not "put a frontend on the scripts." The right move is:

1. extract the core domain logic behind stable service interfaces
2. replace JSON-file state with a real database
3. expose controlled backend APIs for scan, review, execute, and settlement
4. build a UI for watchlists, approvals, orders, fills, positions, and P&L

## What Is Already Reusable

These parts of `Edge_Radar` are valuable and should inform the app design:

- `scripts/kalshi/kalshi_client.py`
  - Real exchange connectivity exists already, including RSA-PSS signing and authenticated order placement.
- `scripts/kalshi/kalshi_executor.py`
  - The risk model is concrete and fairly mature: edge floor, score floor, confidence floor, open-position cap, per-event cap, concentration cap, max-bet cap, batch-aware Kelly sizing.
- `scripts/kalshi/edge_detector.py`
  - There is actual market classification and edge computation logic, not just placeholders.
- `scripts/shared/opportunity.py`
  - There is already a coherent domain object for scored opportunities.
- `scripts/shared/trade_log.py`
  - Fill-aware accounting logic exists, which matters if you want correct exposure and P&L.
- `tests/test_risk_gates.py` and `tests/test_fill_accounting.py`
  - These are good indicators that the most sensitive execution logic is testable and worth preserving.
- `scripts/kalshi/sql/init_db.sql`
  - There is already a rough data model for trades, positions, opportunities, calibration, and alerts, even though it is not the system of record today.

## Why It Is Not Yet a Web App Backend

The repo currently behaves like a local operator console, not a multi-user application:

- Entry points are CLI scripts, mostly routed through `scripts/scan.py`.
- State is stored in local JSON files under `data/`.
- Configuration is mostly `.env`-driven and global to the machine.
- There is no HTTP API, session/auth layer, or role model.
- There is no transactional persistence around orders, fills, positions, and reconciliation.
- Long-running scans and executions are synchronous script flows.
- Output is terminal tables and markdown reports, not structured API responses.

The biggest architectural gap is not frontend. It is the missing application/service layer.

## Recommended Product Shape

### Target MVP

Build a web app that supports:

- login for one operator account at minimum
- connect one Kalshi account securely
- run scans by market type and filter
- review scored opportunities before execution
- place bets manually from reviewed opportunities
- track open positions, resting orders, fills, settled results, and daily P&L
- enforce the existing risk gates server-side on every execution request
- keep an auditable order and decision history

### Do Not Build First

Avoid these in v1:

- multi-user trading desks
- automatic background betting without explicit approval
- broker-agnostic support beyond Kalshi
- copying every CLI/reporting feature into the UI
- agentic prompt workflows as a primary control surface

## Recommended Architecture

### Backend

Use `FastAPI` for the app/API layer.

Why:

- native fit with the existing Python logic
- easy background jobs and typed request/response models
- straightforward path from current scripts to services

Suggested backend modules:

- `app/api`
  - REST endpoints for scans, opportunities, orders, positions, fills, settlements, settings
- `app/services`
  - orchestration layer that calls extracted scanner/risk/execution logic
- `app/domain`
  - `Opportunity`, `OrderRequest`, `RiskDecision`, `Position`, `Settlement`
- `app/integrations`
  - Kalshi API wrapper adapted from `kalshi_client.py`
- `app/jobs`
  - scheduled scan, fill refresh, settlement sync, nightly reconciliation
- `app/repositories`
  - database persistence

### Frontend

Use `Next.js` or `React` with a dashboard-style UI.

Core screens:

- Overview
  - bankroll, open risk, daily P&L, pending orders, settlement summary
- Scan Runner
  - choose market type, filters, thresholds, run scan
- Opportunity Review
  - sortable table of opportunities with edge, confidence, score, fair value, price, rationale
- Trade Ticket
  - preview size, cost, risk-gate result, and final confirmation
- Orders and Fills
  - resting, partial, filled, rejected
- Positions
  - grouped by event and category
- Settlements and Performance
  - realized P&L, CLV, win rate, calibration
- Settings
  - account, default sizing, thresholds, API connectivity status

### Database

Use Postgres for the app. SQLite is fine only for a prototype.

Reason:

- you need transactional safety around order creation, fill sync, and reconciliation
- JSON files will become brittle immediately once background jobs and UI actions overlap

Suggested first-class tables:

- users
- brokerage_accounts
- scan_runs
- opportunities
- risk_decisions
- orders
- fills
- positions
- settlements
- bankroll_snapshots
- strategy_settings
- audit_events

The existing `scripts/kalshi/sql/init_db.sql` is useful as a starting reference, but it should not be adopted as-is without normalization and migration tooling.

### Background Jobs

Add a job runner for:

- scheduled scans
- order status refresh
- fill synchronization
- settlement ingestion
- daily portfolio rollups

This can be done with:

- FastAPI background tasks plus APScheduler for a simple setup, or
- Celery/RQ plus Redis if you expect heavier automation

For MVP, APScheduler is enough.

## Best Implementation Strategy

### Option A: Thin Wrapper Around Existing Scripts

Not recommended except as a throwaway prototype.

Pros:

- fastest to demo
- minimal refactor initially

Cons:

- brittle subprocess orchestration
- hard to return structured errors and results
- hard to test end-to-end
- unsafe concurrency once UI and jobs both run
- global `.env` and local files become operational hazards

This is acceptable only if the goal is a private desktop-like control panel for one operator and a short lifespan.

### Option B: Extract Core Logic Into Importable Services

Recommended.

Approach:

- keep the mathematical and exchange logic
- move script-only concerns to adapters
- convert terminal/report output into typed return objects

Specifically extract:

- edge calculation from `edge_detector.py`
- risk sizing and gating from `kalshi_executor.py`
- fill accounting from `trade_log.py`
- Kalshi execution methods from `kalshi_client.py`

Then build new APIs on top of those services.

This gives you a real application and preserves the parts of the repo that are actually differentiated.

## Concrete Refactor Map

If this becomes implementation work later, I would do it in this order:

1. Extract domain package
   - `Opportunity`
   - `RiskDecision`
   - `ExecutionPreview`
   - `ExecutionResult`
2. Extract scan service
   - scanner functions should return structured Python objects only
   - no `rich` output, no file writes
3. Extract risk service
   - isolate `size_order()` and gate evaluation from CLI flow
4. Extract execution service
   - submit order
   - persist order attempt
   - sync fills
5. Replace JSON storage
   - opportunities, trades, settlements, open positions go into DB-backed repositories
6. Add FastAPI endpoints
7. Add background reconciliation jobs
8. Add web UI

## Suggested API Surface

Minimum useful API endpoints:

- `POST /api/scans`
  - run a scan with filters
- `GET /api/scans/{id}`
  - scan status and results
- `GET /api/opportunities`
  - query saved opportunities
- `POST /api/opportunities/{id}/preview-order`
  - risk-check and size without placing
- `POST /api/opportunities/{id}/execute`
  - place an order after preview/confirmation
- `GET /api/orders`
  - submitted orders with fill state
- `GET /api/positions`
  - open positions
- `GET /api/settlements`
  - closed positions and P&L
- `GET /api/portfolio/summary`
  - bankroll, exposure, P&L, open risk
- `POST /api/sync/fills`
  - manual refresh
- `POST /api/sync/settlements`
  - manual refresh

## Key Risks To Address Early

### 1. State Consistency

The current system mixes live exchange state and local file state. A web app cannot rely on that.

You need one source of truth:

- exchange is source of truth for balances, orders, fills, and positions
- app database is source of truth for internal audit, opportunity history, UI state, and derived analytics

### 2. Idempotency

Execution endpoints must not place duplicate orders on refresh, retries, or double-clicks.

Add:

- client-generated idempotency key
- server-side execution record before exchange submission
- duplicate market/order locks

### 3. Secrets Handling

The current local private-key-file model works for scripts. For a web app, you need:

- encrypted secret storage
- environment-level secret injection
- no raw key-path assumptions in request handlers

### 4. Concurrency

Today, a single operator running a script controls order flow. A web app adds:

- user clicks
- scheduled jobs
- fill sync jobs
- settlement jobs

You need locking around:

- scan-triggered execution
- order submission
- position refresh

### 5. Compliance and Platform Constraints

Because the goal is placing and tracking bets, you should assume product, legal, and platform review is mandatory before exposing it beyond personal/internal use.

At minimum, plan for:

- jurisdiction and account restrictions
- audit logs
- operator approvals
- responsible-use guardrails
- terms-of-service review for connected platforms and data providers

## Recommended MVP Scope

A realistic MVP would be:

- single-user authenticated web app
- Kalshi only
- manual scan initiation
- manual approval required before execution
- automatic fill/settlement sync
- portfolio dashboard
- history and P&L
- server-side enforcement of the existing risk model

This is enough to become useful without overbuilding.

## What I Would Keep vs Replace

Keep:

- Kalshi API signing and connectivity patterns
- market/opportunity model concepts
- risk rules and sizing logic
- fill-based accounting logic
- core edge models where they are already producing value
- regression tests around money logic

Replace:

- subprocess-based orchestration
- terminal-first presentation
- JSON-file persistence
- global `.env`-driven per-machine state
- markdown-report-based workflows as primary outputs

## Recommendation

If the objective is a real working betting web app, this project is a good candidate to become one, but only if you treat `Edge_Radar` as the source of trading logic rather than the full app foundation.

My recommended path is:

1. build a new FastAPI + Postgres backend
2. port the reusable scan/risk/execution logic into importable services
3. build a React/Next.js dashboard on top
4. keep the current script repo unchanged until the service layer is proven

That gives you a controlled migration path without destabilizing the existing project.

## Suggested Next Step

The highest-value next deliverable would be a short technical design package for the new app:

- system architecture diagram
- database schema draft
- API contract draft
- MVP screen list
- migration plan from script engine to app services

If you want, I can produce that package next in this `artifacts/Edge-Radar-App` folder without touching `Edge_Radar`.
