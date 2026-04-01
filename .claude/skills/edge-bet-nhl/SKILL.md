---
name: edge-bet-nhl
description: Quick-fire NHL betting — scans tomorrow's NHL games for edge and executes bets with preset defaults.
argument-hint: [overrides] — e.g., "--unit-size 1", "--date today", "--max-bets 3", "--pick '1,3'"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep
---

# Bet NHL

Quick-fire NHL betting with preset defaults. Scans for edge, shows preview, then executes on confirmation.

## Defaults

| Setting | Value |
|---------|-------|
| Sport | NHL |
| Unit size | $0.50 |
| Max bets | 10 |
| Min edge | 3% (0.03) |
| Date | tomorrow |
| Exclude open | yes |

Any default can be overridden via arguments: `$ARGUMENTS`

## Execution Steps

### Step 1: Check Status

```bash
python scripts/kalshi/kalshi_executor.py status
```

If daily loss limit is breached, **STOP** — inform the user, no bets today.

### Step 2: Scan

Run the scan with defaults (apply any overrides from arguments):

```bash
python scripts/scan.py sports \
  --filter nhl \
  --unit-size 0.5 \
  --max-bets 10 \
  --min-edge 0.03 \
  --date tomorrow \
  --exclude-open
```

### Step 3: Present & Confirm

Show the opportunity table. Summarize:
- Number of opportunities found
- Top picks and why they have edge (plain language)
- Total estimated cost

Then ask: **"Ready to execute? (or pass --pick to cherry-pick rows)"**

### Step 4: Execute

Once confirmed:

```bash
python scripts/scan.py sports \
  --filter nhl \
  --unit-size 0.5 \
  --max-bets 10 \
  --min-edge 0.03 \
  --date tomorrow \
  --exclude-open \
  --execute
```

If user passed `--pick '1,3,5'`, add that flag.

### Step 5: Report

Summarize: orders placed, total cost, updated balance. Remind to run `/edge-radar settle` after games complete.
