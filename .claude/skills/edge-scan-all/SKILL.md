---
name: edge-scan-all
description: Scan all 4 major sports (MLB, NBA, NHL, NFL) for tomorrow's edge opportunities — preview only, no execution.
argument-hint: [overrides] — e.g., "--date today", "--min-edge 0.05", "--save"
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep
---

# Scan All Sports

Runs edge detection across all 4 major sports for tomorrow. Preview only — no bets placed. Use the individual `/bet-mlb`, `/bet-nba`, `/bet-nhl`, `/bet-nfl` skills to execute.

## Defaults

| Setting | Value |
|---------|-------|
| Sports | MLB, NBA, NHL, NFL |
| Min edge | 3% (0.03) |
| Date | tomorrow |
| Exclude open | yes |
| Execute | no (preview only) |
| Save | yes |

Any default can be overridden via arguments: `$ARGUMENTS`

## Execution Steps

### Step 1: Check Status

```bash
python scripts/kalshi/kalshi_executor.py status
```

Report current balance, open positions, and daily P&L.

### Step 2: Run All 4 Scans

Run each sport sequentially. Apply any argument overrides to all scans.

```bash
python scripts/scan.py sports --filter mlb --min-edge 0.03 --date tomorrow --exclude-open --save
```

```bash
python scripts/scan.py sports --filter nba --min-edge 0.03 --date tomorrow --exclude-open --save
```

```bash
python scripts/scan.py sports --filter nhl --min-edge 0.03 --date tomorrow --exclude-open --save
```

```bash
python scripts/scan.py sports --filter nfl --min-edge 0.03 --date tomorrow --exclude-open --save
```

### Step 3: Combined Summary

After all 4 scans complete, present a unified summary:

| Sport | Opportunities | Top Edge | Est. Cost (at $0.50/unit, max 10) |
|-------|--------------|----------|-----------------------------------|
| MLB | X found | Y% | $Z |
| NBA | X found | Y% | $Z |
| NHL | X found | Y% | $Z |
| NFL | X found | Y% | $Z |
| **Total** | **X** | | **$Z** |

Then list the top 5 opportunities across all sports ranked by edge.

Remind the user: **"Use `/bet-mlb`, `/bet-nba`, `/bet-nhl`, or `/bet-nfl` to execute bets for a specific sport."**
