---
name: edge-radar-coordination
description: Coordinate between Edge-Radar agents (Edge-Hunter, Edge-Gatekeeper, Edge-Auditor, Edge-Radar-Scriptor) via the ax CLI. Use when sending inter-agent messages, delegating work, assigning tasks, or publishing deliverables (reports, calibration updates, betting analyses). ALL cross-agent coordination MUST go through ax-cli — never coordinate via direct filesystem, ad-hoc scripts, or out-of-band channels. Triggers: "message Edge-Hunter", "ask the Gatekeeper", "hand off to Auditor", "publish calibration", "upload this report for the team", "tell the team", "assign task to another agent".
---

# Edge-Radar Coordination

You are one of the Edge-Radar agents. The team collaborates exclusively through the aX Platform via the `ax` CLI. This skill tells you how to talk to the team, delegate work, and publish deliverables so other agents can use them.

## The Three Rules (non-negotiable)

### 1. When messaging another agent, wait for their reply

Use the default `--wait` behavior when sending targeted messages to another Edge-Radar agent. Do **not** pass `--skip-ax` on direct peer-to-peer messages — that ends the conversation prematurely and the other agent's reply never comes back to you.

```bash
# Correct — waits for the reply, keeps the conversation alive
ax send --to Edge-Hunter "What's the confidence on this OPPORTUNITY?"

# Use a longer timeout if you expect a considered reply
ax send --to Edge-Gatekeeper --timeout 180 "Can you confirm the watch:NBA-LAL key is populated?"

# Threaded continuation (use --reply-to to keep the same conversation)
ax send --reply-to <prior-message-id> --to Edge-Hunter "Follow-up: what about the second method's result?"
```

`--skip-ax` is acceptable for broadcasts (no `--to`) — e.g., posting a calibration update to the whole team with no single recipient expected to reply.

### 2. When delegating work, create a task AND announce it on the board

Never create a task silently. The target agent's listener may not wake on a bare task — and even if it does, the rest of the team has no visibility. Do both:

```bash
# 1. Create and assign the task
ax tasks create "Re-scan NBA moneylines with updated injury status" --priority high --assign Edge-Hunter

# 2. Immediately announce on the message board — mention the team AND the specific agent
ax send --to Edge-Hunter "@Edge-Gatekeeper @Edge-Auditor FYI — I've opened a task for @Edge-Hunter to re-scan NBA moneylines after the LeBron OUT ruling. Task priority: high."
```

The message-board announcement must:
- Mention the specific agent being assigned (`@Edge-Hunter`)
- Tag the rest of the Edge-Radar team so they have context (`@Edge-Gatekeeper @Edge-Auditor` — omit the ones irrelevant to the workflow if it's noisy)
- Briefly state **what** the task is, **why**, and the priority

### 3. Upload deliverables as aX context — not day-to-day activity

**DO upload to aX context** (shared team memory — other agents read it):

| Deliverable | Example key |
|:-----------|:------------|
| Calibration reports / adjustment factors | `calibration:nba_ml` |
| Settlement summaries | `settlement:2026-04-21` |
| Scan result snapshots (validated opportunities) | `scan:sports:2026-04-21` |
| Rejected-scan validation logs (for Auditor) | `scan:rejected:2026-04-21` |
| Multi-source price matrices | `prices:<ticker>` |
| Watch-list entries for open positions | `watch:<ticker>` |
| Risk state | `risk:daily_pnl`, `risk:open_count` |
| Active threat alerts | `alert:<ticker>:<type>` |

```bash
# Set a structured context key
ax context set calibration:nba_ml '{"bias": 0.04, "factor": 0.96, "n": 52, "effective": "2026-04-21"}'

# Upload a file as a named artifact
ax upload file reports/calibration/2026-04-21.md --key "calibration:nba_ml:report"
```

**DO NOT upload to aX context:**
- Individual bet-by-bet chatter or transient P&L updates
- Day-to-day conversation transcripts between agents
- Scratch intermediate computations
- Personal reasoning traces or debugging logs

Those belong in local logs (`data/history/…`, `reports/…`) or the message board transcript, not context. Context is shared memory; keep it tidy.

## Who's on the Team

| Handle (aX) | Phase | What they own |
|:------------|:------|:--------------|
| `Edge-Hunter` | Pre-trade | Parallel scans, two-method validation, calibration-adjusted edge, OPPORTUNITY publishing |
| `Edge-Gatekeeper` | Trade | 9 execution gates, Kelly sizing, Kalshi RSA order placement, `watch:<ticker>` writes |
| `Edge-Auditor` | Post-trade | Live position monitoring, settlement, calibration feedback loop, ALERT publishing |
| `Edge-Radar-Scriptor` | Cross-cutting | Orchestration, Telegram routing, config management, human escalation |

> Note on naming: CLAUDE.md files and older docs sometimes use snake_case (`@edge_hunter`). In the aX CLI you must use the canonical PascalCase-hyphenated handles above (`Edge-Hunter`). Use those exact strings with `--to`.

## Primary Message Contracts (who sends what)

| Message | From → To | When |
|:--------|:----------|:-----|
| `OPPORTUNITY` | Hunter → Gatekeeper | Validated edge passes both methods |
| `EXECUTED` | Gatekeeper → Auditor | Order filled; `watch:<ticker>` written |
| `REJECTED` | Gatekeeper → Hunter | Opportunity failed a gate (with reason) |
| `ALERT` | Auditor → Gatekeeper | Position at risk (close/reduce/hold recommendation) |
| `CALIBRATION UPDATE` | Auditor → Hunter | Post-settlement bias corrections (requires n ≥ 20) |

## The ax-cli — Always Your First Tool

Inter-agent coordination means `ax` or nothing. Don't coordinate via direct filesystem pokes at other agents' dirs, manual config edits, or out-of-band messaging. The ax message log, task ledger, and context store are the team's source of truth — if it isn't in ax, it didn't happen.

### Identity (run at session start)

```bash
ax auth whoami            # confirm bound_agent is *your* agent, not user
```

If `bound_agent` is `None` or a different agent, stop and fix your config before sending anything — otherwise you'll post as the user (see `.ax/config.toml`, token must start with `axp_a_`).

### Messaging quick reference

```bash
# Targeted message, wait for reply (DEFAULT — use this for P2P conversation)
ax send --to <Agent-Handle> "message"

# Team-wide broadcast (skip-ax OK since no single recipient expected)
ax send --skip-ax "Team update: settlement batch complete for 2026-04-21"

# Threaded reply
ax send --reply-to <message-id> "response"

# Read the board
ax messages list --limit 20
ax messages search "OPPORTUNITY"
ax messages get <message-id> --json

# Delete a misattributed or superseded message
ax messages delete <message-id>
```

### Tasks

```bash
ax tasks create "title" --priority <low|medium|high> --assign <Agent-Handle>
ax tasks list                              # your queue
ax tasks update <task-id> --status completed
```

### Context (shared memory)

```bash
# Write
ax context set <key> '<value or JSON>'
ax upload file <path> --key "<key>"

# Read
ax context get <key>
ax context list --prefix "<namespace>:"
ax context download <key> --output <path>
```

### Listening / waiting

```bash
# Wait for a specific agent to ping you
ax watch --from <Agent-Handle> --timeout 300

# Poll for @mentions
ax listen --agent <Your-Handle>
```

## Decision Guide

Use this when you're about to coordinate something:

```
Need another agent's input or decision?
    → ax send --to <agent> ...  (wait for reply; don't --skip-ax)

Need another agent to do work for you?
    → ax tasks create --assign <agent>    (1st)
    → ax send announcing the task          (2nd, MUST)

Finished a deliverable the team needs?
    → Is it reusable shared knowledge (report, calibration, scan result)?
        Yes → ax context set / ax upload   (publish it)
        No  → leave it in local logs       (day-to-day chatter)

Urgent position-risk event (Auditor only)?
    → ax send --to Edge-Gatekeeper  (ALERT format, don't batch)
    → never --skip-ax on urgent alerts
```

## Anti-patterns

| Don't | Do instead |
|:------|:-----------|
| `ax send --to X ... --skip-ax` for a P2P question | Use default wait so you get the reply |
| Create a task without announcing it | Create task **and** post a mention on the board |
| `ax context set chatter:daily '…'` | Put day-to-day chatter in local logs, not context |
| Edit another agent's config/files directly | Send them a message or assign them a task |
| Post from a user PAT (sender shows as `michaelschecht`) | Verify `ax auth whoami` shows `bound_agent` = your handle; rotate token if not |
| Batch urgent ALERTs | Send immediately, one message per trigger |
