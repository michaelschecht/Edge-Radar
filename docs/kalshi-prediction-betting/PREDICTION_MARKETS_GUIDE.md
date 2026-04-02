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
- [TV Mention Markets](#tv-mention-markets)
- [Companies](#companies)
- [Politics & Government](#politics--government)
- [Tech & Science](#tech--science)
- [Culture & Entertainment](#culture--entertainment)
- [Key Differences from Sports Betting](#key-differences-from-sports-betting)

---

## Quick Reference

See [Scripts Reference](../SCRIPTS_REFERENCE.md) for complete CLI flags. Key command:

```bash
python scripts/scan.py prediction --filter <filter>
```

For risk gates and position sizing rules, see [Architecture](../ARCHITECTURE.md). For enhancement history, see [Roadmap](../enhancements/ROADMAP.md).
See also: [Sports Guide](../kalshi-sports-betting/SPORTS_GUIDE.md) | [Futures Guide](../kalshi-futures-betting/FUTURES_GUIDE.md)

---

## Market Categories

| Category | Filter | Ticker Prefixes | Edge Detection | Data Source |
|----------|--------|----------------|----------------|-------------|
| Crypto | `crypto` | KXBTC, KXETH, KXXRP, KXDOGE, KXSOL | **Yes** | CoinGecko (free) |
| Weather | `weather` | KXHIGHNY, KXHIGHCHI, KXHIGHMIA, KXHIGHDEN | **Yes** | NWS API (free) |
| S&P 500 | `spx` | KXINX | **Yes** | Yahoo Finance + VIX (free) |
| TV Mentions | `mentions` | KXLASTWORDCOUNT, KXPOLITICSMENTION, KXFOXNEWSMENTION, KXNBAMENTION | **Yes** | Historical settlement rates |
| Companies | `companies` | KXBANKRUPTCY, KXIPO | **Partial** | Historical baseline (bankruptcy), browse only (IPO) |
| Politics | `politics` | KXIMPEACH | **Yes** | Time-decay hazard model |
| Tech/Science | `techscience` | KXQUANTUM, KXFUSION | **Yes** | Time-decay hazard model |
| Economics / Fed | -- | KXFED, KXCPI, KXGDP | Not yet | -- |
| Commodities | -- | KXWTI | Not yet | -- |

---

## Crypto

Edge detection uses **CoinGecko** for live prices and 7-day price history to compute realized volatility, then models the probability of price being above/below each strike using a log-normal distribution.

### Bitcoin (KXBTC)

**Example market:** "Bitcoin price range on Mar 22, 2026?"

**Settlement:** Daily at 4:00 PM EDT based on CF Benchmarks Real-Time Index.

### Ethereum (KXETH)

### Other Crypto

| Filter | Asset | Ticker Prefix |
|--------|-------|---------------|
| `xrp` | Ripple (XRP) | KXXRP |
| `doge` | Dogecoin | KXDOGE |
| `sol` | Solana | KXSOL |

---

## Weather

Edge detection uses the **NWS (National Weather Service) API** for temperature forecasts, then models the probability of the actual high exceeding each strike using a normal distribution with uncertainty that increases by forecast horizon (~2.5 degrees F for tomorrow, ~3.5 degrees F for 2 days out, etc.).

### Available Cities

| Filter Prefix | City | NWS Office |
|---------------|------|------------|
| KXHIGHNY | New York City | OKX |
| KXHIGHCHI | Chicago | LOT |
| KXHIGHMIA | Miami | MFL |
| KXHIGHDEN | Denver | BOU |

**Example market:** "Will the high temp in NYC be >61 degrees on Mar 23, 2026?"

**Settlement:** End of day based on official NWS/weather station readings.

**Confidence levels:**
- **High** -- settlement is tomorrow (NWS most accurate)
- **Medium** -- 2-3 days out
- **Low** -- 4+ days out (accuracy degrades)

---

## Stock Market Indices (S&P 500)

Edge detection uses **Yahoo Finance** for the current SPX price and **VIX** for implied volatility, then models the probability of SPX being above/below each strike using Black-Scholes-style probability estimation.

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

**Example market:** "Will the upper bound of the federal funds rate be above 4.25% following the June 2026 FOMC meeting?"

**Settlement:** After the FOMC announcement (8 meetings/year).

**Research tips:**
- CME FedWatch tool shows market-implied probabilities
- Compare Kalshi prices to FedWatch -- discrepancies are potential edges
- Key inputs: CPI, jobs data, Fed speeches, dot plot

### CPI / Inflation (KXCPI)

**Example market:** "Will CPI rise more than 1.0% in May 2026?"

**Settlement:** After BLS CPI release (monthly, usually mid-month).

### GDP Growth (KXGDP)

**Example market:** "Will real GDP increase by more than 4.5% in Q1 2026?"

**Settlement:** After BEA advance GDP estimate (quarterly).

---

## Commodities

> **Note:** No automated edge detection yet.

### Crude Oil / WTI (KXWTI)

**Example market:** "Will the WTI front-month settle oil price be >$99.99 on Mar 24, 2026?"

**Settlement:** Daily based on NYMEX WTI front-month settlement price.

---

## TV Mention Markets

Edge detection uses **historical settlement rates** from Kalshi's own settled markets. For KXLASTWORDCOUNT (numeric), a Poisson model is built from past episode word counts. For binary mention markets, the overall YES settlement rate is used as a baseline fair value.

### Lawrence O'Donnell Word Count (KXLASTWORDCOUNT)

**Example market:** "How many times will Lawrence O'Donnell say Trump during next The Last Word?"

**Settlement:** After the broadcast airs. Actual count is reported.

**Edge model:** Poisson distribution fitted to historical episode counts. Compares P(count >= strike) to market price.

### Binary Mention Markets

| Prefix | What It Tracks |
|--------|---------------|
| KXPOLITICSMENTION | Will speaker say keyword on political broadcast? |
| KXFOXNEWSMENTION | Will keyword be said on Fox News? |
| KXNBAMENTION | Will announcer say keyword during NBA game? |

**Settlement:** After the broadcast airs (yes/no).

**Edge model:** Historical YES rate across all settled markets in the series. Common political words (Trump, Republican, etc.) get a boosted fair value.

---

## Companies

### Corporate Bankruptcies (KXBANKRUPTCY)

Edge detection uses a **historical baseline projection** (~750 corporate bankruptcies/year average) with normal distribution modeling.

**Example market:** "How many corporate bankruptcies will there be this year?"

**Settlement:** Year-end based on official filing counts.

### IPO Markets (KXIPO)

Browse only -- no automated edge detection (company-specific events require qualitative research).

**Example market:** "Who will IPO in 2026?"

**Settlement:** When the company officially IPOs (or year-end if it doesn't).

---

## Politics & Government

### Impeachment (KXIMPEACH)

Edge detection uses a **time-decay hazard model** with calibrated annual probability estimates (~12%/year).

**Example market:** "Will the President be impeached before Jan 1, 2028?"

**Settlement:** When impeachment proceedings begin (or deadline passes).

**Edge model:** Exponential survival function: P(event by deadline) = 1 - exp(-lambda * years). Confidence is always "low" since these are speculative base-rate models.

---

## Tech & Science

### Quantum Computing (KXQUANTUM) & Nuclear Fusion (KXFUSION)

Same time-decay hazard model as political events, with lower annual probabilities (~5% quantum, ~3% fusion).

**Example markets:**
- "When will the first useful quantum computer be developed?"
- "When will nuclear fusion be achieved?"

**Settlement:** When the event occurs (or deadline passes).

---

## Culture & Entertainment

Currently limited availability. Kalshi periodically adds markets for awards shows (Oscars, Emmys), box office, and other cultural events. Browse using the Kalshi client.

---

## Key Differences from Sports Betting

| Aspect | Sports Betting | Prediction Markets |
|--------|---------------|-------------------|
| **Edge detection** | Sportsbook odds (The Odds API) | CoinGecko, NWS, VIX, historical rates, time-decay models |
| **Settlement speed** | Hours (after game ends) | Varies: daily, monthly, or event-driven |
| **Liquidity** | Generally high for major sports | Varies widely by market |
| **Data sources** | 8-12 sportsbooks de-vigged | Asset prices, weather forecasts, vol models, settlement history |
| **Volatility** | Game outcomes are one-shot | Prices move continuously until settlement |
| **Strategy** | Statistical edge from de-vigged odds | Probability modeling against strike prices |

### When Prediction Markets Have the Most Edge

1. **Weather 1-3 days out** -- NWS forecasts are highly accurate but markets often overprice uncertainty
2. **Crypto during high volatility** -- strike prices may be mispriced relative to realized vol
3. **S&P 500 near close** -- short time to expiry with known VIX = tight probability estimates
4. **TV mention markets** -- historical settlement rates reveal systematic mispricings, especially for common words
5. **Right after data releases** -- markets can be slow to reprice (e.g., CPI comes in hot, Fed rate markets haven't moved yet)
6. **Long-dated political events** -- time-decay model can spot overpriced impeachment/tech timeline markets
