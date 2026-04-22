# Betting Scenarios: Kelly Sizing Across Max-Bets and Unit-Size

Nine worked scenarios showing how `KELLY_FRACTION`, `--max-bets`, and `--unit-size` interact.

---

## Fixed Assumptions (All Scenarios)

| Parameter | Value |
|---|---|
| Bankroll | $100.00 (available cash from Kalshi) |
| KELLY_FRACTION | 0.5 |
| Open bets/wagers | None |
| Market price | $0.50 per contract (all opportunities) |
| Concentration cap | 20% of bankroll = $20.00 max per bet |
| Max bet (sports) | $50.00 per bet |

### Five Opportunities (Ranked by Edge)

| # | Edge | Composite Score | Confidence |
|---|------|----------------|------------|
| 1 | 80% | 9.5 | high |
| 2 | 60% | 8.5 | high |
| 3 | 40% | 7.5 | high |
| 4 | 20% | 7.0 | medium |
| 5 | 10% | 6.5 | medium |

---

## Formula Recap

```
flat_contracts  = max(1, round(unit_size / market_price))
effective_kelly = KELLY_FRACTION / batch_size
kelly_bet       = effective_kelly x edge x bankroll
kelly_contracts = max(1, floor(kelly_bet / market_price))

final_contracts = max(flat_contracts, kelly_contracts)
cost            = final_contracts x market_price
```

Where `batch_size = min(number_of_opportunities, max_bets)`.

After sizing, caps apply in order: concentration (20%), then max bet ($50), then bankroll.

---

## Scenario 1: `--max-bets 10`

```
batch_size = min(5 opportunities, 10) = 5
effective_kelly = 0.5 / 5 = 0.10
All 5 opportunities execute
```

### 1A: `--unit-size 1.00`

**Flat contracts:** round($1.00 / $0.50) = **2 contracts** ($1.00)

| # | Edge | Kelly Bet | Kelly Contracts | Flat | Final Contracts | Cost | Winner |
|---|------|-----------|-----------------|------|-----------------|------|--------|
| 1 | 80% | 0.10 x 0.80 x $100 = $8.00 | floor(8.00/0.50) = 16 | 2 | 16 | $8.00 | Kelly |
| 2 | 60% | 0.10 x 0.60 x $100 = $6.00 | floor(6.00/0.50) = 12 | 2 | 12 | $6.00 | Kelly |
| 3 | 40% | 0.10 x 0.40 x $100 = $4.00 | floor(4.00/0.50) = 8 | 2 | 8 | $4.00 | Kelly |
| 4 | 20% | 0.10 x 0.20 x $100 = $2.00 | floor(2.00/0.50) = 4 | 2 | 4 | $2.00 | Kelly |
| 5 | 10% | 0.10 x 0.10 x $100 = $1.00 | floor(1.00/0.50) = 2 | 2 | 2 | $1.00 | Tie |

**Total cost: $21.00** (21% of bankroll) | No caps triggered

### 1B: `--unit-size 0.50`

**Flat contracts:** round($0.50 / $0.50) = **1 contract** ($0.50)

| # | Edge | Kelly Contracts | Flat | Final Contracts | Cost | Winner |
|---|------|-----------------|------|-----------------|------|--------|
| 1 | 80% | 16 | 1 | 16 | $8.00 | Kelly |
| 2 | 60% | 12 | 1 | 12 | $6.00 | Kelly |
| 3 | 40% | 8 | 1 | 8 | $4.00 | Kelly |
| 4 | 20% | 4 | 1 | 4 | $2.00 | Kelly |
| 5 | 10% | 2 | 1 | 2 | $1.00 | Kelly |

**Total cost: $21.00** (21% of bankroll) | No caps triggered

### 1C: `--unit-size 0.25`

**Flat contracts:** max(1, round($0.25 / $0.50)) = **1 contract** ($0.50)

| # | Edge | Kelly Contracts | Flat | Final Contracts | Cost | Winner |
|---|------|-----------------|------|-----------------|------|--------|
| 1 | 80% | 16 | 1 | 16 | $8.00 | Kelly |
| 2 | 60% | 12 | 1 | 12 | $6.00 | Kelly |
| 3 | 40% | 8 | 1 | 8 | $4.00 | Kelly |
| 4 | 20% | 4 | 1 | 4 | $2.00 | Kelly |
| 5 | 10% | 2 | 1 | 2 | $1.00 | Kelly |

**Total cost: $21.00** (21% of bankroll) | No caps triggered

### Scenario 1 Takeaway

With `--max-bets 10` (batch_size=5), Kelly sizing produces identical results regardless of unit size. The flat floor never wins because even the weakest edge (10%) generates enough Kelly contracts to match or beat the flat amount. **Changing unit size has zero effect here.**

---

## Scenario 2: `--max-bets 5`

```
batch_size = min(5 opportunities, 5) = 5
effective_kelly = 0.5 / 5 = 0.10
All 5 opportunities execute
```

**This is mathematically identical to Scenario 1.** The batch_size is `min(opportunities, max_bets)`, and since there are exactly 5 opportunities, `min(5, 10)` and `min(5, 5)` both equal 5.

### 2A: `--unit-size 1.00` — Same as 1A

| # | Edge | Final Contracts | Cost |
|---|------|-----------------|------|
| 1 | 80% | 16 | $8.00 |
| 2 | 60% | 12 | $6.00 |
| 3 | 40% | 8 | $4.00 |
| 4 | 20% | 4 | $2.00 |
| 5 | 10% | 2 | $1.00 |

**Total cost: $21.00**

### 2B: `--unit-size 0.50` — Same as 1B

**Total cost: $21.00**

### 2C: `--unit-size 0.25` — Same as 1C

**Total cost: $21.00**

### Scenario 2 Takeaway

`--max-bets` only changes the math when it's **less than** the number of opportunities. Setting it higher than the opportunity count has no additional effect — the batch divisor is already capped at the opportunity count.

---

## Scenario 3: `--max-bets 2`

```
batch_size = min(5 opportunities, 2) = 2
effective_kelly = 0.5 / 2 = 0.25
Only the top 2 approved bets execute (approved[:max_bets])
```

This is where things change. The Kelly divisor drops from 5 to 2, making each bet **2.5x more aggressive**. But only 2 bets execute.

### 3A: `--unit-size 1.00`

**Flat contracts:** round($1.00 / $0.50) = **2 contracts** ($1.00)

| # | Edge | Kelly Bet | Kelly Contracts | Flat | Raw Cost | Cap Check | Final Contracts | Final Cost |
|---|------|-----------|-----------------|------|----------|-----------|-----------------|------------|
| 1 | 80% | 0.25 x 0.80 x $100 = $20.00 | 40 | 2 | $20.00 | 20% of bankroll = $20 (at limit) | 40 | $20.00 |
| 2 | 60% | 0.25 x 0.60 x $100 = $15.00 | 30 | 2 | $15.00 | 15% < 20% (OK) | 30 | $15.00 |

Bets 3-5 are sized but **not executed** (only top 2 proceed):

| # | Edge | Kelly Contracts | Would-Be Cost | Status |
|---|------|-----------------|---------------|--------|
| 3 | 40% | 20 | $10.00 | Not executed |
| 4 | 20% | 10 | $5.00 | Not executed |
| 5 | 10% | 5 | $2.50 | Not executed |

**Total cost: $35.00** (35% of bankroll) | Bet 1 at concentration limit

### 3B: `--unit-size 0.50`

**Flat contracts:** round($0.50 / $0.50) = **1 contract** ($0.50)

| # | Edge | Kelly Contracts | Flat | Final Contracts | Final Cost |
|---|------|-----------------|------|-----------------|------------|
| 1 | 80% | 40 | 1 | 40 | $20.00 |
| 2 | 60% | 30 | 1 | 30 | $15.00 |

**Total cost: $35.00** (35% of bankroll) | Same result — Kelly dominates

### 3C: `--unit-size 0.25`

**Flat contracts:** max(1, round($0.25 / $0.50)) = **1 contract** ($0.50)

| # | Edge | Kelly Contracts | Flat | Final Contracts | Final Cost |
|---|------|-----------------|------|-----------------|------------|
| 1 | 80% | 40 | 1 | 40 | $20.00 |
| 2 | 60% | 30 | 1 | 30 | $15.00 |

**Total cost: $35.00** (35% of bankroll) | Same result — Kelly dominates

### Scenario 3 Takeaway

Fewer `--max-bets` means a **smaller Kelly divisor**, which means **larger individual bets**. Total cost jumped from $21 to $35, even though only 2 bets execute instead of 5. The top bet hits the 20% concentration cap — the first time a cap fires across all scenarios.

---

## Summary: All Nine Scenarios

| Scenario | --max-bets | --unit-size | batch_size | Bets Executed | Total Cost | % of Bankroll |
|----------|-----------|-------------|------------|---------------|------------|---------------|
| 1A | 10 | $1.00 | 5 | 5 | $21.00 | 21% |
| 1B | 10 | $0.50 | 5 | 5 | $21.00 | 21% |
| 1C | 10 | $0.25 | 5 | 5 | $21.00 | 21% |
| 2A | 5 | $1.00 | 5 | 5 | $21.00 | 21% |
| 2B | 5 | $0.50 | 5 | 5 | $21.00 | 21% |
| 2C | 5 | $0.25 | 5 | 5 | $21.00 | 21% |
| 3A | 2 | $1.00 | 2 | 2 | $35.00 | 35% |
| 3B | 2 | $0.50 | 2 | 2 | $35.00 | 35% |
| 3C | 2 | $0.25 | 2 | 2 | $35.00 | 35% |

---

## Key Insights

### 1. Unit size is irrelevant when edges are high

Across all 9 scenarios, `--unit-size` changed nothing. This is because the flat floor only wins when Kelly produces **fewer** contracts than the flat amount. With edges of 10%+, a KELLY_FRACTION of 0.5, and a $100 bankroll, Kelly always produces enough contracts to match or exceed even the $1.00 flat floor.

**When does unit size actually matter?** When edges are small. For flat to win, you need:

```
effective_kelly x edge x bankroll < unit_size

Example (batch=5):
0.10 x edge x $100 < $1.00
edge < 10%
```

With edges below ~10%, the flat floor kicks in and guarantees a minimum bet size. In real markets where edges are typically 3-8%, unit size becomes the **primary sizing driver**.

### 2. `--max-bets` is the dominant control

It controls two things simultaneously:
- **How many bets execute** (approved[:max_bets])
- **How aggressive each bet is** (Kelly divided by batch_size)

Fewer max_bets = fewer but larger bets. More max_bets = more but smaller bets.

### 3. `--max-bets` beyond opportunity count does nothing

`--max-bets 10` and `--max-bets 5` were identical because batch_size = min(opportunities, max_bets). With 5 opportunities, anything above 5 has no effect.

### 4. Concentration cap is the first hard wall

The 20% concentration cap ($20 on a $100 bankroll) fired on the 80% edge bet in Scenario 3. Without it, that bet would have been $20 anyway (coincidence at these numbers), but at higher bankrolls or more aggressive Kelly fractions, this cap prevents any single bet from dominating the portfolio.

### 5. The real-world implication

For typical Kalshi sports markets with 3-8% edges:

| Setting | Effect |
|---|---|
| Higher `--unit-size` | Increases the minimum bet (flat floor matters more) |
| Higher `KELLY_FRACTION` | Scales up bets proportionally (more aggressive) |
| Lower `--max-bets` | Bigger individual bets, fewer total bets |
| Higher bankroll | Kelly bets scale linearly with bankroll |

---

## Appendix: When Flat Sizing Wins (Realistic Edge Example)

To illustrate when unit size matters, here's a single bet with a realistic 5% edge:

```
bankroll = $100, KELLY_FRACTION = 0.5, market_price = $0.50
batch_size = 5, effective_kelly = 0.10
edge = 0.05 (5%)
```

| Sizing Method | unit=$1.00 | unit=$0.50 | unit=$0.25 |
|---|---|---|---|
| Flat contracts | 2 | 1 | 1 |
| Kelly bet | 0.10 x 0.05 x $100 = $0.50 | same | same |
| Kelly contracts | floor(0.50/0.50) = 1 | 1 | 1 |
| **Final contracts** | **2 (flat wins)** | **1 (tie)** | **1 (tie)** |
| **Cost** | **$1.00** | **$0.50** | **$0.50** |

At 5% edge, flat sizing with `--unit-size 1.00` produces **double** the bet compared to `--unit-size 0.50`. This is the regime where unit size drives your position sizing.
