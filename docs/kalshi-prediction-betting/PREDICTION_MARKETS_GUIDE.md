# Kalshi Prediction Markets -- Betting Guide

Non-sports prediction markets on Kalshi covering crypto, weather, S&P 500, economics, politics, and more.

---

## Table of Contents

- [Quick Reference](#quick-reference)
- [Market Categories](#market-categories)
- [Crypto](#crypto)
- [Weather](#weather)
- [Stock Market Indices (S&P 500)](#stock-market-indices-sp-500)
- [Economics & Federal Reserve](#economics--federal-reserve)
- [Commodities](#commodities)
- [Politics & Government](#politics--government)
- [IPOs & Corporate](#ipos--corporate)
- [Culture & Entertainment](#culture--entertainment)
- [How to Bet on Prediction Markets](#how-to-bet-on-prediction-markets)
- [Key Differences from Sports Betting](#key-differences-from-sports-betting)

---

## Quick Reference

For crypto, weather, and S&P 500 markets, use the **prediction scanner** which has dedicated edge detection with external data sources:

```bash
# Prediction scanner (crypto, weather, S&P 500)
python scripts/prediction/prediction_scanner.py scan                    # All prediction markets
python scripts/prediction/prediction_scanner.py scan --filter crypto    # All crypto
python scripts/prediction/prediction_scanner.py scan --filter btc       # Bitcoin only
python scripts/prediction/prediction_scanner.py scan --filter weather   # Weather
python scripts/prediction/prediction_scanner.py scan --filter spx       # S&P 500
python scripts/prediction/prediction_scanner.py scan --filter eth --save  # Save to watchlist
```

For other prediction markets (Fed, CPI, commodities, politics) that don't have dedicated edge detectors yet, see the [Economics](#economics--federal-reserve), [Commodities](#commodities), and [Politics](#politics--government) sections below.

---

## Market Categories

| Category | Ticker Prefixes | Edge Detection | Data Source |
|----------|----------------|----------------|-------------|
| Crypto | KXBTC, KXETH, KXXRP, KXDOGE, KXSOL | **Yes** | CoinGecko (free) |
| Weather | KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHDEN | **Yes** | NWS API (free) |
| S&P 500 | KXINX | **Yes** | Yahoo Finance + VIX (free) |
| Economics / Fed | KXFED, KXCPI, KXGDP | Not yet | -- |
| Commodities | KXWTI | Not yet | -- |
| Politics | KXPOLITICSMENTION, KXFOXNEWSMENTION, KXLASTWORDCOUNT | Not yet | -- |
| IPOs | KXIPO | Not yet | -- |

---

## Crypto

Edge detection uses **CoinGecko** for live prices and 7-day price history to compute realized volatility, then models the probability of price being above/below each strike using a log-normal distribution.

### Bitcoin (KXBTC)

```bash
python scripts/prediction/prediction_scanner.py scan --filter btc
python scripts/prediction/prediction_scanner.py scan --filter btc --min-edge 0.05
```

**Example market:** "Bitcoin price range on Mar 22, 2026?"

**Settlement:** Daily at 4:00 PM EDT based on CF Benchmarks Real-Time Index.

### Ethereum (KXETH)

```bash
python scripts/prediction/prediction_scanner.py scan --filter eth
```

### Other Crypto

| Filter | Asset | Ticker Prefix |
|--------|-------|---------------|
| `xrp` | Ripple (XRP) | KXXRP |
| `doge` | Dogecoin | KXDOGE |
| `sol` | Solana | KXSOL |

```bash
python scripts/prediction/prediction_scanner.py scan --filter xrp
python scripts/prediction/prediction_scanner.py scan --filter doge
```

### All Crypto Combined

```bash
python scripts/prediction/prediction_scanner.py scan --filter crypto
python scripts/prediction/prediction_scanner.py scan --filter crypto --save
```

---

## Weather

Edge detection uses the **NWS (National Weather Service) API** for temperature forecasts, then models the probability of the actual high exceeding each strike using a normal distribution with uncertainty that increases by forecast horizon (~2.5°F for tomorrow, ~3.5°F for 2 days out, etc.).

### Available Cities

| Filter Prefix | City | NWS Office |
|---------------|------|------------|
| KXHIGHNY | New York City | OKX |
| KXHIGHCHI | Chicago | LOT |
| KXHIGHMIA | Miami | MFL |
| KXHIGHDEN | Denver | BOU |

```bash
# All weather markets
python scripts/prediction/prediction_scanner.py scan --filter weather

# Specific city (use raw ticker prefix)
python scripts/prediction/prediction_scanner.py scan --filter KXHIGHNY
python scripts/prediction/prediction_scanner.py scan --filter KXHIGHCHI
python scripts/prediction/prediction_scanner.py scan --filter KXHIGHMIA
python scripts/prediction/prediction_scanner.py scan --filter KXHIGHDEN
```

**Example market:** "Will the high temp in NYC be >61° on Mar 23, 2026?"

**Settlement:** End of day based on official NWS/weather station readings.

**Confidence levels:**
- **High** -- settlement is tomorrow (NWS most accurate)
- **Medium** -- 2-3 days out
- **Low** -- 4+ days out (accuracy degrades)

---

## Stock Market Indices (S&P 500)

Edge detection uses **Yahoo Finance** for the current SPX price and **VIX** for implied volatility, then models the probability of SPX being above/below each strike using Black-Scholes-style probability estimation.

```bash
python scripts/prediction/prediction_scanner.py scan --filter spx
python scripts/prediction/prediction_scanner.py scan --filter spx --min-edge 0.05
python scripts/prediction/prediction_scanner.py scan --filter sp500   # alias
```

**Example market:** "Will the S&P 500 be above 6949.99 on Mar 27, 2026 at 4pm EDT?"

**Settlement:** Daily at 4:00 PM EDT based on official closing price.

**Strategy notes:**
- These are essentially daily binary options on SPX
- Multiple strike prices available (like an options chain)
- VIX is used for volatility -- when VIX is high, more strikes are in play
- Short-dated markets (1-5 days) tend to be most liquid

---

## Economics & Federal Reserve

> **Note:** These categories don't have automated edge detection yet. Use the Kalshi client to browse markets manually.

### Fed Funds Rate (KXFED)

Will the Fed raise, hold, or cut rates at the next FOMC meeting?

```bash
python scripts/kalshi/kalshi_client.py markets --limit 20 --status open
# Then filter manually by KXFED prefix, or:
python scripts/kalshi/edge_detector.py scan --filter KXFED
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
```

**Example market:** "Will CPI rise more than 1.0% in May 2026?"

**Settlement:** After BLS CPI release (monthly, usually mid-month).

### GDP Growth (KXGDP)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXGDP
```

**Example market:** "Will real GDP increase by more than 4.5% in Q1 2026?"

**Settlement:** After BEA advance GDP estimate (quarterly).

---

## Commodities

> **Note:** No automated edge detection yet.

### Crude Oil / WTI (KXWTI)

```bash
python scripts/kalshi/edge_detector.py scan --filter KXWTI
```

**Example market:** "Will the WTI front-month settle oil price be >$99.99 on Mar 24, 2026?"

**Settlement:** Daily based on NYMEX WTI front-month settlement price.

---

## Politics & Government

> **Note:** No automated edge detection yet.

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

> **Note:** No automated edge detection yet.

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
python scripts/kalshi/kalshi_client.py markets --limit 50 --status open
```

Kalshi periodically adds markets for awards shows (Oscars, Emmys), box office, and other cultural events.

---

## How to Bet on Prediction Markets

### Step 1: Scan for Opportunities

```bash
# Use the prediction scanner for crypto, weather, S&P 500
python scripts/prediction/prediction_scanner.py scan --filter crypto
python scripts/prediction/prediction_scanner.py scan --filter weather
python scripts/prediction/prediction_scanner.py scan --filter spx

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
# Preview first (uses the sports executor with raw prefix filter)
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
| **Edge detection** | Sportsbook odds (The Odds API) | CoinGecko, NWS, Yahoo Finance + VIX |
| **Settlement speed** | Hours (after game ends) | Varies: daily, monthly, or event-driven |
| **Liquidity** | Generally high for major sports | Varies widely by market |
| **Data sources** | 8-12 sportsbooks de-vigged | Asset prices, weather forecasts, vol models |
| **Volatility** | Game outcomes are one-shot | Prices move continuously until settlement |
| **Strategy** | Statistical edge from de-vigged odds | Probability modeling against strike prices |

### When Prediction Markets Have the Most Edge

1. **Weather 1-3 days out** -- NWS forecasts are highly accurate but markets often overprice uncertainty
2. **Crypto during high volatility** -- strike prices may be mispriced relative to realized vol
3. **S&P 500 near close** -- short time to expiry with known VIX = tight probability estimates
4. **Right after data releases** -- markets can be slow to reprice (e.g., CPI comes in hot, Fed rate markets haven't moved yet)
5. **Niche markets** -- less liquid markets (IPOs, mentions) are less efficient
