# Edge-Radar Web Frontend — Options Analysis

**Goal:** Remote bet placement and scan review from any device.

---

## Architecture Advantages

The existing codebase is well-structured for a web layer:

- **`execute_pipeline()`** takes a client + list of opportunities, returns structured dicts — clean API boundary
- **`scan_all_markets()`** returns `list[Opportunity]` dataclass instances — serializable
- **`KalshiClient`** uses stateless per-request RSA auth — no session management needed
- All config flows through `os.getenv()` via `shared/config.py`

**One refactoring required (all options):** Scanner functions currently print via `rich` console. A web layer needs data returned separately from presentation. Solution: a thin service layer (~50-100 lines) that captures or suppresses `rprint` output when called from the API.

---

## Option 1: FastAPI Backend + Simple Frontend

**Build time: 2-3 days**

Wrap existing functions as REST endpoints. Pair with a simple HTML/JS frontend or iOS Shortcuts.

| Aspect | Assessment |
|---|---|
| Remote access | Excellent — VPS, Tailscale, or Cloudflare Tunnel |
| Security | First-class OAuth2/JWT; API keys stay server-side |
| Mobile | Responsive HTML with Tailwind; iOS Shortcuts can call endpoints directly |
| Code reuse | 85-90% — all logic reused, new code is ~200 lines for the API |

**Endpoints would map to:**
- `POST /scan` → `scan_all_markets()` + `execute_pipeline(execute=False)`
- `POST /execute` → `execute_pipeline(execute=True)`
- `GET /status` → balance, positions, P&L
- `POST /settle` → `settle_trades()`
- `GET /risk` → risk dashboard

**Best overall option.** Maximum flexibility, clean separation, most natural fit for existing function signatures.

---

## Option 2: Streamlit Dashboard

**Build time: 1 day**

Python-only dashboard. Dropdowns for sport filter, buttons for scan/execute, tables for results.

| Aspect | Assessment |
|---|---|
| Remote access | Good — same VPS/tunnel approach, but stateful sessions can timeout |
| Security | Basic password protection only; pair with Cloudflare Access for real auth |
| Mobile | Mediocre — desktop-first, tables overflow on small screens |
| Code reuse | 80% — lose `rich` formatting, need `st.session_state` for multi-step flows |

**Fastest to prototype but you'll outgrow it.** Good for a "do I even want a web UI?" experiment. Becomes limiting with background scans, notifications, or multi-step workflows.

---

## Option 3: Telegram Bot

**Build time: 1-2 days**

Message commands from your phone: `/scan mlb`, `/status`, `/execute 1,3,5`.

| Aspect | Assessment |
|---|---|
| Remote access | Excellent — works behind NAT, no VPS needed (long-polling) |
| Security | Hardcode your Telegram user ID to reject all other senders; API keys stay local |
| Mobile | Excellent — Telegram is already on your phone, native notifications |
| Code reuse | 85% — all logic reused, new code is command handlers + message formatting |

**Best effort-to-remote-access ratio.** Conversational flow maps naturally to scan → review → pick → execute. Tradeoff: no visual dashboard, everything is chat-based.

**Note:** Bot messages are NOT end-to-end encrypted (only Telegram Secret Chats are). Scan results traverse Telegram's servers in plaintext.

---

## Option 4: Progressive Web App (PWA)

**Build time: 4-5 days**

Option 1 + polished mobile frontend with home-screen install and push notifications.

| Aspect | Assessment |
|---|---|
| Remote access | Excellent (same as Option 1) |
| Security | Same as Option 1 |
| Mobile | Best of all options — full-screen app, home-screen icon, push notifications |
| Code reuse | 85-90% backend, 0% frontend (all new) |

**Only pursue if mobile UX is the top priority.** Option 1 with simple HTML gets 80% of the way for half the effort.

---

## Option 5: Discord Bot

**Build time: 1-2 days**

Same as Telegram but in Discord. Slash commands with autocomplete, embedded rich messages, multiple channels (#scans, #executions, #pnl).

Functionally equivalent to Telegram. **Only prefer if you already live in Discord.**

---

## Option 6: Claude Code Scheduled Triggers

**Build time: < 1 hour**

Use `RemoteTrigger` and `schedule` skill to run scans on cron and email results via `agentmail`.

| Aspect | Assessment |
|---|---|
| Remote access | Limited — trigger runs but can't interactively review/pick |
| Security | No new attack surface; runs with local credentials |
| Mobile | Poor — no native interface |
| Code reuse | 100% — runs existing scripts unchanged |

**Good for automated daily scans, poor for interactive remote betting.** Best used as a complement to another option.

---

## Recommended Phased Approach

| Phase | What | Time | Result |
|---|---|---|---|
| **1** | Telegram Bot | Day 1 | Remote scan + execute from your phone |
| **2** | FastAPI Backend | Day 2-3 | REST API; Telegram becomes a client of the API |
| **3** | Simple Web Dashboard | Day 4-5 | HTML dashboard calling FastAPI endpoints |
| **4** | Claude Scheduled Scans | Already done | Morning scan at 8 AM, emailed via agentmail |

Phase 1 gets you remote access immediately. Phase 2 decouples interface from logic. Phase 3 adds a visual dashboard. Phase 4 is already partially in place with the existing scheduled tasks.

---

## Key Files for Implementation

| File | Role in Web Layer |
|---|---|
| `scripts/kalshi/kalshi_executor.py` | `execute_pipeline()` — core function to wrap |
| `scripts/kalshi/edge_detector.py` | `scan_all_markets()` — primary scanner to expose |
| `scripts/shared/config.py` | Centralized config; web layer reads same values |
| `scripts/kalshi/risk_check.py` | Portfolio status → maps to `/status` endpoint |
| `scripts/shared/opportunity.py` | `Opportunity` dataclass → defines API response schema |
