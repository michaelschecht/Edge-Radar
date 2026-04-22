# Betting Math & Position Sizing Guide

How `KELLY_FRACTION`, `UNIT_SIZE`, `--max-bets`, and risk caps interact during scans and `--execute` runs.

---

## Key Variables

| Variable | What It Does |
|---|---|
| `KELLY_FRACTION` | Fraction of Kelly criterion to use (aggressiveness dial) |
| `--unit-size` / `UNIT_SIZE` | Dollar floor per bet — the minimum you'll wager |
| `--max-bets` | Cap on how many bets per run; also divides Kelly to prevent over-commitment |
| `market_price` | Kalshi contract price (0.00–1.00), i.e. the implied probability |
| `edge` | Your estimated probability minus the market price |
| `bankroll` | Your **available cash balance** from Kalshi API (not portfolio value) |

---

## The Two Sizing Methods

Every bet is sized using **both** methods, and the system always takes **whichever is larger**. Flat is the floor; Kelly scales up when edge is significant.

### 1. Flat Unit Sizing (Floor)

```
contracts = round(unit_size / market_price)
cost      = contracts x market_price
```

With `--unit-size 0.50` and a market price of $0.25:

```
contracts = round(0.50 / 0.25) = 2 contracts
cost      = 2 x $0.25 = $0.50
```

### 2. Kelly Sizing (Scales with Edge)

```
effective_kelly = KELLY_FRACTION / max_bets
kelly_bet       = effective_kelly x edge x bankroll
kelly_contracts = floor(kelly_bet / market_price)
```

Kelly sizing grows with edge and bankroll, but is **divided by batch size** to prevent over-committing when placing multiple simultaneous bets.

### Final Result

```
contracts = max(flat_contracts, kelly_contracts)
cost      = contracts x market_price
```

---

## Worked Example

**Parameters:** `KELLY_FRACTION=0.5`, `--unit-size 0.5`, `--max-bets 10`

**Scenario:** bankroll = $500, one opportunity with `market_price = $0.40`, `edge = 0.08` (8%)

### Flat Sizing

```
contracts = round(0.50 / 0.40) = 1 contract
cost      = 1 x $0.40 = $0.40
```

### Kelly Sizing

```
effective_kelly = 0.5 / 10 = 0.05
kelly_bet       = 0.05 x 0.08 x $500 = $2.00
kelly_contracts = floor($2.00 / $0.40) = 5 contracts
cost            = 5 x $0.40 = $2.00
```

### Result

Kelly (5 contracts, $2.00) > Flat (1 contract, $0.40), so **5 contracts at $2.00 total cost**.

---

## Why `--max-bets` Matters

Kelly gets **divided by batch size**. With the same numbers but `--max-bets 1`:

```
effective_kelly = 0.5 / 1 = 0.5
kelly_bet       = 0.5 x 0.08 x $500 = $20.00
kelly_contracts = floor($20.00 / $0.40) = 50 contracts
cost            = 50 x $0.40 = $20.00
```

That's **10x larger** than the `--max-bets 10` result. The batch divisor prevents committing full-Kelly across many simultaneous bets.

---

## Cap Sequence (Applied After Sizing)

After computing contracts, three caps fire **in order**. Each recalculates `contracts = floor(limit / market_price)`:

| Order | Cap | Limit |
|---|---|---|
| 1 | **Concentration** | 20% of bankroll (`MAX_POSITION_CONCENTRATION`) |
| 2 | **Max bet size** | $50 sports / $100 prediction (`MAX_BET_SIZE_SPORTS` / `MAX_BET_SIZE_PREDICTION`) |
| 3 | **Bankroll** | Cannot exceed available cash balance |

---

## Do Pre-Existing Wagers Affect Sizing?

**Yes, but indirectly — through risk gates, not the sizing formula itself.**

The sizing math (Kelly + flat) runs **fresh every time**. However, existing positions affect the inputs and gates:

| Gate | How Existing Wagers Matter |
|---|---|
| **Bankroll** | Pulled live from Kalshi — money locked in open positions reduces available balance, which shrinks Kelly bets |
| **Open position count** | Current positions count toward `MAX_OPEN_POSITIONS` (10). Newly-approved bets in the same run also increment this counter |
| **Duplicate ticker** | If you already hold a market, the new bet is auto-rejected |
| **Per-event cap** | If you have 3 bets on the same game already, new ones on that game are rejected |
| **Daily P&L** | If today's settled losses hit `-$MAX_DAILY_LOSS`, all new bets are rejected |

---

## Total Cost Per Run

The sum of each approved bet's cost:

```
total_cost = SUM(contracts_i x market_price_i)  for all approved bets
```

There is no separate batch-level cap. Each bet is sized individually with the batch divisor baked in, and the per-bet caps apply independently.

---

## Nine Risk Gates (All Must Pass)

Before any trade executes, these gates are checked in order. Failures 1–7 **reject** the bet entirely. Gates 8–9 **cap** the size downward.

| # | Gate | Rejects or Caps |
|---|---|---|
| 1 | Daily loss limit not breached | Reject |
| 2 | Open position count under max | Reject |
| 3 | Edge >= minimum threshold (3%) | Reject |
| 4 | Composite score >= minimum (6.0) | Reject |
| 5 | Confidence >= minimum level | Reject |
| 6 | Not already holding this ticker | Reject |
| 7 | Per-event cap not exceeded (3 per game) | Reject |
| 8 | Single position <= max concentration (20%) | Cap |
| 9 | Bet size <= category max ($50/$100) | Cap |

---

## Quick Reference: CLI Flags

```bash
# Preview with custom sizing
python scripts/scan.py sports --filter mlb --date today \
    --unit-size 0.50 --max-bets 10

# Execute with custom sizing
python scripts/scan.py sports --filter mlb --date today \
    --unit-size 0.50 --max-bets 10 --execute
```

Environment variables (`.env`) set the defaults; CLI flags override them per-run.
