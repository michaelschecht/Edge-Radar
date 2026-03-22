# Kalshi Prediction Markets -- Betting Guide

Non-sports prediction markets on Kalshi covering economics, finance, crypto, weather, politics, and culture.

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [Market Categories](#market-categories)
- [Economics & Federal Reserve](#economics--federal-reserve)
- [Stock Market Indices](#stock-market-indices)
- [Crypto](#crypto)
- [Commodities](#commodities)
- [Weather](#weather)
- [Politics & Government](#politics--government)
- [IPOs & Corporate](#ipos--corporate)
- [Culture & Entertainment](#culture--entertainment)
- [How to Bet on Prediction Markets](#how-to-bet-on-prediction-markets)
- [Key Differences from Sports Betting](#key-differences-from-sports-betting)

---

## Quick Reference

```bash
# Browse any prediction market category by ticker prefix
python scripts/kalshi/edge_detector.py scan --filter <PREFIX>

# Examples
python scripts/kalshi/edge_detector.py scan --filter KXINX       # S&P 500
python scripts/kalshi/edge_detector.py scan --filter KXBTC        # Bitcoin
python scripts/kalshi/edge_detector.py scan --filter KXFED        # Fed rate decisions
python scripts/kalshi/edge_detector.py scan --filter KXHIGHNY     # NYC weather

# Check a specific market
python scripts/kalshi/kalshi_client.py market --ticker <FULL_TICKER>

# Place a bet (via executor with raw prefix filter)
python scripts/kalshi/kalshi_executor.py run --filter KXBTC --execute --max-bets 3
```

> **Note:** Automated edge detection currently works for sports markets only. Prediction markets can be scanned and bet on, but edge is estimated from market microstructure (liquidity, spread) rather than cross-referenced external odds.

---

## Market Categories

| Category | Ticker Prefixes | Settlement |
|----------|----------------|------------|
| Economics / Fed | KXFED, KXCPI, KXGDP, KXPPI, KXPCE | After official data release |
| Stock Indices | KXINX | Daily at 4pm EDT |
| Crypto | KXBTC, KXETH, KXXRP, KXDOGE | Daily at 4pm EDT |
| Commodities | KXWTI | Daily close |
| Weather | KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHDEN | End of day (local) |
| Politics | KXPOLITICSMENTION, KXFOXNEWSMENTION, KXLASTWORDCOUNT | After broadcast |
| IPOs | KXIPO | When event occurs |
| Announcer mentions | KXNBAMENTION | After broadcast |

---

## Economics & Federal Reserve

### Fed Funds Rate (KXFED)

Will the Fed raise, hold, or cut rates at the next FOMC meeting?

```bash
python scripts/kalshi/edge_detector.py scan --filter KXFED
python scripts/kalshi/kalshi_executor.py run --filter KXFED --execute --max-bets 3
```

**Example market:** "Will the upper bound of the federal funds rate be above 4.25% following the June 2026 FOMC meeting?"

**Settlement:** After the FOMC announcement (8 meetings/year).

**Research tips:**
- CME FedWatch tool shows market-implied probabilities
- Compare Kalshi prices to FedWatch -- discrepancies are potential edges
- Key inputs: CPI, jobs data, Fed speeches, dot plot

### CPI / Inflation (KXCPI)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXCPI
python scripts/kalshi/kalshi_executor.py run --filter KXCPI --execute --max-bets 3
```

**Example market:** "Will CPI rise more than 1.0% in May 2026?"

**Settlement:** After BLS CPI release (monthly, usually mid-month).

### GDP Growth (KXGDP)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXGDP
python scripts/kalshi/kalshi_executor.py run --filter KXGDP --execute --max-bets 3
```

**Example market:** "Will real GDP increase by more than 4.5% in Q1 2026?"

**Settlement:** After BEA advance GDP estimate (quarterly).

---

## Stock Market Indices

### S&P 500 (KXINX)

Binary options on whether the S&P 500 closes above or below a specific level.

```bash
python scripts/kalshi/edge_detector.py scan --filter KXINX
python scripts/kalshi/kalshi_executor.py run --filter KXINX --execute --max-bets 5
```

**Example market:** "Will the S&P 500 be above 6949.99 on Mar 27, 2026 at 4pm EDT?"

**Settlement:** Daily at 4:00 PM EDT based on official closing price.

**Strategy notes:**
- These are essentially daily binary options on SPX
- Multiple strike prices available (like an options chain)
- Short-dated markets (1-5 days) are most liquid
- Compare to SPX options implied vol for edge

---

## Crypto

### Bitcoin (KXBTC)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXBTC
python scripts/kalshi/kalshi_executor.py run --filter KXBTC --execute --max-bets 3
```

**Example market:** "Bitcoin price range on Mar 22, 2026?"

**Settlement:** Daily at 4:00 PM EDT.

### Ethereum (KXETH)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXETH
python scripts/kalshi/kalshi_executor.py run --filter KXETH --execute --max-bets 3
```

### Other Crypto

| Prefix | Asset |
|--------|-------|
| KXXRP | Ripple (XRP) |
| KXDOGE | Dogecoin |

```bash
python scripts/kalshi/edge_detector.py scan --filter KXXRP
python scripts/kalshi/edge_detector.py scan --filter KXDOGE
```

---

## Commodities

### Crude Oil / WTI (KXWTI)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXWTI
python scripts/kalshi/kalshi_executor.py run --filter KXWTI --execute --max-bets 3
```

**Example market:** "Will the WTI front-month settle oil price be >$99.99 on Mar 24, 2026?"

**Settlement:** Daily based on NYMEX WTI front-month settlement price.

---

## Weather

Temperature markets for major US cities. Will the high temperature exceed a threshold?

### Available Cities

| Prefix | City |
|--------|------|
| KXHIGHNY | New York City |
| KXHIGHCHI | Chicago |
| KXHIGHMIA | Miami |
| KXHIGHDEN | Denver |

```bash
# NYC weather
python scripts/kalshi/edge_detector.py scan --filter KXHIGHNY
python scripts/kalshi/kalshi_executor.py run --filter KXHIGHNY --execute --max-bets 3

# Chicago weather
python scripts/kalshi/edge_detector.py scan --filter KXHIGHCHI

# Miami weather
python scripts/kalshi/edge_detector.py scan --filter KXHIGHMIA

# Denver weather
python scripts/kalshi/edge_detector.py scan --filter KXHIGHDEN
```

**Example market:** "Will the high temp in NYC be >61 degrees on Mar 23, 2026?"

**Settlement:** End of day based on official NWS/weather station readings.

**Research tips:**
- Compare Kalshi prices to NWS forecasts and ensemble models
- Weather markets tend to be less efficient than sports -- potential for edge
- Short-dated (1-3 day) forecasts are most reliable for finding mispricing

---

## Politics & Government

### TV Mention Markets

| Prefix | What It Tracks |
|--------|---------------|
| KXPOLITICSMENTION | Political keyword mentions on broadcast |
| KXFOXNEWSMENTION | Fox News specific mentions |
| KXLASTWORDCOUNT | Lawrence O'Donnell word counts |
| KXNBAMENTION | NBA broadcast announcer mentions |

```bash
python scripts/kalshi/edge_detector.py scan --filter KXPOLITICSMENTION
python scripts/kalshi/edge_detector.py scan --filter KXFOXNEWSMENTION
python scripts/kalshi/edge_detector.py scan --filter KXLASTWORDCOUNT
```

**Settlement:** After the broadcast airs.

---

## IPOs & Corporate

### IPO Markets (KXIPO)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXIPO
```

**Example market:** "Who will IPO in 2026?"

**Settlement:** When the company officially IPOs (or year-end if it doesn't).

---

## Culture & Entertainment

Currently limited availability. Check for new markets periodically:

```bash
# Browse all open markets for cultural/entertainment events
python scripts/kalshi/kalshi_client.py markets --limit 50 --status open
```

Kalshi periodically adds markets for awards shows (Oscars, Emmys), box office, and other cultural events.

---

## How to Bet on Prediction Markets

### Step 1: Browse Available Markets

```bash
# Scan a category
python scripts/kalshi/edge_detector.py scan --filter KXBTC

# Or look up a specific ticker
python scripts/kalshi/kalshi_client.py market --ticker KXBTC-26MAR22-B87000
```

### Step 2: Understand the Contract

Every Kalshi prediction market is a **binary contract**:
- **YES** = you think the event will happen (price = $0.01 to $0.99)
- **NO** = you think the event won't happen
- **Payout** = $1.00 per contract if you're right, $0.00 if wrong
- **Your cost** = the price you pay per contract
- **Your profit** = $1.00 - price (if correct)

**Example:** You buy "Bitcoin above $90,000?" at $0.35 (YES side)
- If BTC is above $90K at settlement: you get $1.00 per contract, profit = $0.65
- If BTC is below $90K: you lose your $0.35 per contract

### Step 3: Place Your Bet

```bash
# Preview first
python scripts/kalshi/kalshi_executor.py run --filter KXBTC

# Then execute
python scripts/kalshi/kalshi_executor.py run --filter KXBTC --execute --max-bets 3 --unit-size 2
```

### Step 4: Monitor and Settle

```bash
# Check positions
python scripts/kalshi/kalshi_executor.py status

# After settlement time, collect results
python scripts/kalshi/kalshi_settler.py settle
python scripts/kalshi/kalshi_settler.py report
```

---

## Key Differences from Sports Betting

| Aspect | Sports Betting | Prediction Markets |
|--------|---------------|-------------------|
| **Edge detection** | Automated (cross-ref sportsbook odds) | Manual research required |
| **Settlement speed** | Hours (after game ends) | Varies: daily, monthly, or event-driven |
| **Liquidity** | Generally high for major sports | Varies widely by market |
| **Data sources** | The Odds API (sportsbook consensus) | CME FedWatch, NWS forecasts, BLS data, etc. |
| **Volatility** | Game outcomes are one-shot | Prices move continuously until settlement |
| **Strategy** | Statistical edge from de-vigged odds | Information edge from faster/better analysis |

### When Prediction Markets Have the Most Edge

1. **Right after data releases** -- markets can be slow to reprice (e.g., CPI comes in hot, Fed rate markets haven't moved yet)
2. **Weather 1-3 days out** -- NWS ensemble models are highly accurate but markets often overprice uncertainty
3. **Crypto during high volatility** -- strike prices may be mispriced relative to implied vol
4. **Niche markets** -- less liquid markets (IPOs, mentions) are less efficient
