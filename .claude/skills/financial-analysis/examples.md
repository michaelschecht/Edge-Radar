# Financial Analysis Skill - Examples

This document provides concrete examples of how to use the financial-analysis skill.

## Example 1: Stock Market Analysis

**User Request:**
```
Run stock market analysis for yesterday
```

**Expected Workflow:**
1. Agent identifies this as "Stock Market Analysis" type
2. Researches previous day's market data using web search
3. Gathers data on:
   - Major indices (S&P 500, NASDAQ, DOW, Russell 2000)
   - Top 10 gainers and losers
   - Sector performance
   - Key news stories
   - Volume and breadth indicators
4. Creates markdown report following Stock Market Analysis structure
5. Saves to GitHub: `financial-advisors/Stock-Market-Analysis/2025-12-29-stock-market-analysis.md`
6. Commits: "Add Stock Market Analysis for 2025-12-29"
7. Pushes to main branch
8. Posts to AX MCP message board: "📊 Stock Market Analysis for December 29, 2025 is now available: https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Stock-Market-Analysis/2025-12-29-stock-market-analysis.md"

**Sample Output Snippet:**
```markdown
# Stock Market Analysis - December 29, 2025

## Market Overview
U.S. equities closed mixed on Friday as year-end positioning and profit-taking dominated trading. The S&P 500 declined 0.3%, while tech-heavy NASDAQ fell 0.7%. The Dow Jones outperformed with a 0.2% gain.

## Major Indices
- **S&P 500**: 4,783.45 (-0.3%, -15.21 points)
- **NASDAQ Composite**: 15,011.35 (-0.7%, -105.28 points)
- **Dow Jones**: 37,689.54 (+0.2%, +75.86 points)
- **Russell 2000**: 2,027.07 (+0.1%, +2.03 points)

## Top Movers
### Gainers
1. **NVDA** (+3.2%) - AI chip demand outlook upgrade from analyst
2. **TSLA** (+2.8%) - Production milestone announcement
...
```

---

## Example 2: Investment Strategy Insights

**User Request:**
```
Generate investment strategy insights for the previous day
```

**Expected Workflow:**
1. Agent identifies this as "Investment Strategy Insights" type
2. Researches:
   - Asset allocation trends
   - Top-performing ETFs by category
   - VIX, put/call ratios, credit spreads
   - Sector rotation signals
   - Yield curve analysis
3. Creates comprehensive strategy report
4. Saves to GitHub: `financial-advisors/Investment-Strategy-Insights/2025-12-29-investment-strategy-insights.md`
5. Commits and pushes
6. Posts to message board: "💡 Investment Strategy Insights for December 29, 2025 is now available: [GitHub link]"

**Sample Output Snippet:**
```markdown
# Investment Strategy Insights - December 29, 2025

## Executive Summary
Current market environment favors defensive positioning with selective growth exposure. Recommend:
- Increase allocation to quality dividend payers
- Maintain moderate cash reserves (8-10%)
- Favor large-cap over small-cap in current environment
- Selective emerging market exposure

## Asset Allocation Analysis
**Recommended Tactical Allocation:**
- Equities: 55% (neutral to slight underweight)
- Fixed Income: 30% (slight overweight)
- Commodities: 5% (neutral)
- Cash/Alternatives: 10% (overweight)

## Top-Performing ETFs
### Equity ETFs (YTD Performance)
1. **QQQ** - Invesco NASDAQ 100 ETF (+42.5% YTD)
2. **XLK** - Technology Select Sector SPDR (+48.2% YTD)
...
```

---

## Example 3: Global Market Developments

**User Request:**
```
Analyze global market developments for yesterday
```

**Expected Workflow:**
1. Agent identifies this as "Global Market Developments" type
2. Researches:
   - European market performance and ECB policy
   - Asian market performance, BOJ and PBOC policies
   - Geopolitical events
   - Currency and commodity markets
   - Upcoming central bank meetings
3. Creates comprehensive global report
4. Saves to GitHub: `financial-advisors/Global-Market-Developments/2025-12-29-global-market-developments.md`
5. Commits and pushes
6. Posts to message board: "🌍 Global Market Developments for December 29, 2025 is now available: [GitHub link]"

**Sample Output Snippet:**
```markdown
# Global Market Developments - December 29, 2025

## Executive Summary
Global markets showed mixed performance as year-end positioning continued. European markets outperformed on ECB commentary, while Asian markets were pressured by China property sector concerns. Central banks remain in holding pattern ahead of 2026 policy decisions.

## European Markets
### Market Performance
- **DAX (Germany)**: 16,741.74 (+0.8%)
- **FTSE 100 (UK)**: 7,733.24 (+0.3%)
- **CAC 40 (France)**: 7,533.96 (+0.6%)
- **Euro Stoxx 50**: 4,521.98 (+0.7%)

### ECB Policy Update
The European Central Bank maintained its current stance with deposit rate at 3.75%. ECB President Lagarde indicated data-dependent approach for 2026, with next meeting scheduled for January 25, 2026. Market pricing in 25bp cut by March 2026.
...
```

---

## Example 4: Earnings & Corporate Events

**User Request:**
```
Create earnings and corporate events report
```

**Expected Workflow:**
1. Agent identifies this as "Earnings & Corporate Events" type
2. Researches:
   - Companies reporting earnings in next 7 days
   - Recent earnings results and call highlights
   - Dividend announcements
   - Stock splits and buyback programs
   - M&A activity
   - Analyst upgrades/downgrades
3. Creates earnings report
4. Saves to GitHub: `financial-advisors/Earnings-And-Corporate-Events/2025-12-29-earnings-corporate-events.md`
5. Commits and pushes
6. Posts to message board: "📈 Earnings & Corporate Events update for December 29, 2025 is now available: [GitHub link]"

**Sample Output Snippet:**
```markdown
# Earnings & Corporate Events - December 29, 2025

## Executive Summary
Q4 earnings season begins in earnest next week with major financial institutions reporting. Recent earnings showed resilient consumer spending but margin pressure in retail sector. Notable M&A activity in healthcare sector.

## Upcoming Earnings (Next 7 Days)
### Notable Reports
| Company | Ticker | Date | Consensus EPS | Key Themes |
|---------|--------|------|---------------|------------|
| JPMorgan Chase | JPM | Jan 12 | $3.97 | Net interest margin, credit quality |
| Bank of America | BAC | Jan 12 | $0.77 | Deposit trends, investment banking |
| Delta Air Lines | DAL | Jan 11 | $1.28 | Holiday travel demand, fuel costs |
...

## Recent Earnings Highlights
### Major Beats
**Nike (NKE)** - Reported Q2 EPS of $1.03 vs. $0.84 est.
- Revenue up 8% YoY to $13.4B
- China sales rebounded +12%
- Raised full-year guidance
- CEO highlighted innovation pipeline success
...
```

---

## Example 5: Market Sentiment Score

**User Request:**
```
Calculate market sentiment score for today
```

**Expected Workflow:**
1. Agent identifies this as "Market Sentiment Score" type
2. **First reads AX MCP message board** to get today's posts from other agents:
   - Stock Market Analysis post and GitHub link
   - Investment Strategy Insights post and GitHub link
   - Global Market Developments post and GitHub link
   - Earnings & Corporate Events post and GitHub link
3. Reads all 4 GitHub reports to gather data
4. Analyzes using CNN Fear & Greed Index methodology
5. Calculates composite score (0-100)
6. Creates sentiment report with breakdown
7. Saves to GitHub: `financial-advisors/Market-Sentiment-Score/2025-12-29-market-sentiment-score.md`
8. Commits and pushes
9. Posts to message board: "🎯 Market Sentiment Score for December 29, 2025: 58/100 (Greed) - Full analysis: [GitHub link]"
10. **Sends team email** with:
    - Subject: "Market Sentiment Score - December 29, 2025"
    - All 6 recipients
    - Summary of sentiment score and reasoning
    - Summary of all 4 other analyses with GitHub links
    - Key takeaways

**Sample Output Snippet:**
```markdown
# Market Sentiment Score - December 29, 2025

## Sentiment Score: 58/100 - Greed

```
Fear ◄─────────────────●─────────────────► Greed
     0    25          58              75   100
```

## Methodology
This score aggregates seven sentiment indicators using the CNN Fear & Greed Index framework, where 0 represents extreme fear and 100 represents extreme greed.

## Component Analysis

### Market Momentum (65/100)
Based on Stock Market Analysis showing S&P 500 down 0.3% but maintaining position near recent highs. 52-week momentum remains positive at +24%.

### Market Breadth (55/100)
Advance/decline line showing mild deterioration with 1.2:1 ratio. However, new 52-week highs (142) exceed new lows (67), indicating underlying strength.

### Volatility (45/100)
VIX closed at 13.8 (+0.5 points), in low range historically but showing slight uptick. This indicates moderate complacency.

### Safe Haven Demand (52/100)
Gold flat at $2,075/oz. Treasury yields rising slightly (10Y at 3.88%), indicating neutral safe haven demand.

### Put/Call Ratios (60/100)
CBOE Put/Call ratio at 0.82, below the neutral 1.0 level, suggesting mild optimism but not extreme.

### Junk Bond Demand (70/100)
High-yield spreads tightened 5bp to 325bp over Treasuries, indicating strong risk appetite in credit markets.

### Stock Price Strength (59/100)
48% of S&P 500 stocks trading above 50-day MA, slightly above neutral 50% level.

## Summary of Today's Analyses

### Stock Market Analysis
Mixed close with defensive leadership. Tech weakness offset by strength in financials and industrials. Year-end positioning evident in light volume.
[Read full analysis →](https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Stock-Market-Analysis/2025-12-29-stock-market-analysis.md)
...
```

**Sample Email:**
```
To: michael.schecht@ax-platform.com, jacob.taunton@ax-platform.com, heath.dorn@ax-platform.com, mikeschecht@gmail.com, jandrewt82@gmail.com, Heathdorn00@yahoo.com
Subject: Market Sentiment Score - December 29, 2025

Team,

Today's Market Sentiment Score: 58/100 - Greed

## Sentiment Analysis
Our analysis indicates markets are in mild "Greed" territory as we approach year-end. The score of 58/100 reflects generally positive sentiment driven by strong credit market performance and favorable momentum indicators, partially offset by neutral volatility readings.

Key drivers include:
- Strong junk bond demand (spreads at 325bp, tightest in 6 months)
- Positive 52-week momentum (+24% for S&P 500)
- Moderately elevated put/call ratios suggesting cautious optimism
- VIX remaining in low range at 13.8

This level of sentiment suggests markets are optimistic but not excessively euphoric, leaving room for further upside while also indicating potential for pullbacks if sentiment indicators shift.

## Summary of Today's Financial Analyses

1. Stock Market Analysis
   Mixed close with S&P 500 down 0.3% on light volume. Tech underperformed while financials and industrials showed strength. Year-end positioning continues to dominate flow.
   Link: https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Stock-Market-Analysis/2025-12-29-stock-market-analysis.md

2. Investment Strategy Insights
   Tactical recommendation to maintain defensive posture with 55% equity allocation. Favor quality dividend payers and large-caps. Moderate cash position (10%) appropriate for current environment.
   Link: https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Investment-Strategy-Insights/2025-12-29-investment-strategy-insights.md

3. Global Market Developments
   European markets outperformed on ECB commentary. Asian markets mixed with China property concerns weighing. Central banks in holding pattern ahead of 2026 policy decisions.
   Link: https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Global-Market-Developments/2025-12-29-global-market-developments.md

4. Earnings & Corporate Events
   Q4 earnings season kicks off next week with major banks. Recent results show consumer resilience but retail margin pressure. Healthcare M&A activity notable.
   Link: https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Earnings-And-Corporate-Events/2025-12-29-earnings-corporate-events.md

5. Market Sentiment Score
   Composite score of 58/100 indicates mild greed with balanced risk appetite across multiple indicators.
   Link: https://github.com/AX-MCP/AX-CommunityWorkspaces/blob/main/financial-advisors/Market-Sentiment-Score/2025-12-29-market-sentiment-score.md

## Key Takeaways
- Market sentiment moderately positive heading into year-end
- Defensive positioning with selective growth exposure recommended
- Monitor earnings season kickoff next week for sentiment shifts
- Global central banks in wait-and-see mode creates stability
- Credit markets showing strong risk appetite

Best regards,
Financial Analysis Agent
```

---

## Quick Reference Commands

Users can trigger this skill with variations like:

- "Run stock market analysis"
- "Do yesterday's market analysis"
- "Generate investment strategy insights"
- "Analyze global markets"
- "Create earnings report"
- "Calculate market sentiment"
- "Run all financial analyses for yesterday"

## Tips for Best Results

1. **Be specific about timeframe**: "yesterday", "previous day", "last week"
2. **Request specific analysis type**: Mention "stock market", "earnings", "global", etc.
3. **For Market Sentiment**: Make sure other 4 analyses are completed first
4. **Batch requests**: Can request multiple analyses in sequence
5. **Follow-up**: Can ask for clarification or additional details after initial report
