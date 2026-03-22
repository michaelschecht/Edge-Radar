# Market Sentiment Score - {DATE}

## Sentiment Score: {X}/100 - {CLASSIFICATION}

```
Extreme Fear ◄───────────────{●}──────────────► Extreme Greed
             0    25    45  {score}  75    100
```

**Classification Breakdown**:
- 0-24: Extreme Fear
- 25-44: Fear
- 45-55: Neutral
- 56-75: Greed
- 76-100: Extreme Greed

---

## Methodology

This Market Sentiment Score uses the CNN Fear & Greed Index framework, aggregating seven key market indicators to gauge investor sentiment. Each component is scored from 0 (maximum fear) to 100 (maximum greed), and the final score is the average of all components.

The score is derived from:
1. Market Momentum
2. Market Breadth
3. Volatility
4. Safe Haven Demand
5. Put/Call Ratios
6. Junk Bond Demand
7. Stock Price Strength

---

## Component Analysis

### 1. Market Momentum ({SCORE}/100)

**Measurement**: S&P 500 vs. 125-day moving average

**Current Data**:
- S&P 500 Current: {price}
- 125-Day MA: {price}
- Distance from MA: {+/-}%

**Score Calculation**:
{Explain how the score was derived - e.g., "S&P 500 is X% above its 125-day MA, indicating strong/weak momentum"}

**Analysis**:
{Based on Stock Market Analysis findings, discuss market momentum}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

### 2. Market Breadth ({SCORE}/100)

**Measurement**: Advance/decline ratio and new highs vs. new lows

**Current Data**:
- Advance/Decline Ratio: {ratio}
- 52-Week New Highs: {count}
- 52-Week New Lows: {count}
- High/Low Ratio: {ratio}
- Stocks Above 50-Day MA: {%}

**Score Calculation**:
{Explain how breadth indicators were synthesized into a score}

**Analysis**:
{Discussion of market breadth health based on Stock Market Analysis}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

### 3. Volatility ({SCORE}/100)

**Measurement**: VIX vs. 50-day average (inverted - lower VIX = higher score)

**Current Data**:
- VIX Current Level: {value}
- VIX 50-Day Average: {value}
- VIX Distance from Average: {+/-}%

**Score Calculation**:
{Explain how VIX was converted to sentiment score - inverted scale}

**Analysis**:
{Discussion of volatility environment based on Investment Strategy Insights}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

### 4. Safe Haven Demand ({SCORE}/100)

**Measurement**: Stock returns vs. bond returns, gold performance (inverted)

**Current Data**:
- S&P 500 Recent Return: {+/-}%
- 10-Year Treasury Recent Return: {+/-}%
- Gold Recent Return: {+/-}%
- Flight-to-Safety Indicator: {High/Medium/Low}

**Score Calculation**:
{Explain how safe haven flows were assessed - lower safe haven demand = higher score}

**Analysis**:
{Discussion based on Global Market Developments and Investment Strategy Insights}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

### 5. Put/Call Ratios ({SCORE}/100)

**Measurement**: CBOE put/call ratio (inverted - lower = higher score)

**Current Data**:
- CBOE Total Put/Call Ratio: {ratio}
- Equity-Only Put/Call Ratio: {ratio}
- Average Put/Call Ratio (20-day): {ratio}

**Score Calculation**:
{Explain how put/call ratios were converted to sentiment score}

**Analysis**:
{Discussion of options market positioning based on Investment Strategy Insights}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

### 6. Junk Bond Demand ({SCORE}/100)

**Measurement**: High-yield spreads vs. investment grade (inverted - tighter spreads = higher score)

**Current Data**:
- High-Yield Spread: {basis points} over Treasuries
- Investment Grade Spread: {basis points} over Treasuries
- HY Spread Change (5-day): {+/-} bps
- Historical Context: {Percentile relative to 1-year range}

**Score Calculation**:
{Explain how credit spreads were converted to sentiment score}

**Analysis**:
{Discussion of credit market risk appetite based on Investment Strategy Insights}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

### 7. Stock Price Strength ({SCORE}/100)

**Measurement**: Number of stocks at 52-week highs vs. lows, stocks above moving averages

**Current Data**:
- Stocks at 52-Week Highs: {count} ({%} of index)
- Stocks at 52-Week Lows: {count} ({%} of index)
- Stocks Above 50-Day MA: {%}
- Stocks Above 200-Day MA: {%}

**Score Calculation**:
{Explain how price strength indicators were synthesized}

**Analysis**:
{Discussion based on Stock Market Analysis and breadth data}

**Contribution to Overall Sentiment**: {How this component affects overall score}

---

## Composite Score Breakdown

| Component | Score | Weight | Contribution |
|-----------|-------|--------|--------------|
| Market Momentum | {X}/100 | 14.3% | {X} points |
| Market Breadth | {X}/100 | 14.3% | {X} points |
| Volatility | {X}/100 | 14.3% | {X} points |
| Safe Haven Demand | {X}/100 | 14.3% | {X} points |
| Put/Call Ratios | {X}/100 | 14.3% | {X} points |
| Junk Bond Demand | {X}/100 | 14.3% | {X} points |
| Stock Price Strength | {X}/100 | 14.3% | {X} points |
| **TOTAL** | **{FINAL}/100** | **100%** | **{FINAL} points** |

---

## Summary of Today's Analyses

### 1. Stock Market Analysis
**Key Findings**:
{2-3 sentence summary of main points from Stock Market Analysis}

**Link**: [Read full analysis →]({GitHub URL})

---

### 2. Investment Strategy Insights
**Key Findings**:
{2-3 sentence summary of main points from Investment Strategy Insights}

**Link**: [Read full analysis →]({GitHub URL})

---

### 3. Global Market Developments
**Key Findings**:
{2-3 sentence summary of main points from Global Market Developments}

**Link**: [Read full analysis →]({GitHub URL})

---

### 4. Earnings & Corporate Events
**Key Findings**:
{2-3 sentence summary of main points from Earnings & Corporate Events}

**Link**: [Read full analysis →]({GitHub URL})

---

### 5. Market Sentiment Score
**This Analysis**:
Market sentiment registered at {score}/100 ({classification}), reflecting {brief characterization of what this score means}.

**Link**: [Read full analysis →]({GitHub URL - this document})

---

## Interpretation

### What This Score Means

{2-3 paragraphs explaining:
- What a score of {X}/100 in the {classification} range indicates about current market psychology
- How this compares to typical market conditions
- What this suggests for market direction and investor behavior}

### Current Market Psychology

**Dominant Emotions**: {Fear/Greed/Uncertainty/Optimism/etc.}

**Investor Behavior Patterns**:
- {Pattern 1: e.g., "Risk-on flows into equities"}
- {Pattern 2: e.g., "Defensive positioning in fixed income"}
- {Pattern 3: e.g., "Sector rotation favoring cyclicals"}

**Contrarian Indicators**:
{Discussion of whether sentiment is at extremes that might signal reversals}

---

## Historical Context

### Recent Sentiment Trends

{If historical data available, show trend}

| Date | Score | Classification | S&P 500 Level |
|------|-------|----------------|---------------|
| {DATE} | {X}/100 | {Classification} | {price} |
| {DATE-1} | {X}/100 | {Classification} | {price} |
| {DATE-2} | {X}/100 | {Classification} | {price} |

**Trend Analysis**:
{Discussion of whether sentiment is improving, deteriorating, or stable}

### Comparison to Key Market Levels

**Current Sentiment vs. Recent Extremes**:
- Recent High: {score}/100 on {date}
- Recent Low: {score}/100 on {date}
- 30-Day Average: {score}/100

**Correlation with Market Performance**:
{If data available, discuss how sentiment has correlated with market direction}

---

## Signals and Implications

### Bullish Signals
{List components or factors supporting continued strength:}
- {Signal 1}
- {Signal 2}
- {Signal 3}

### Bearish Signals
{List components or factors suggesting caution:}
- {Signal 1}
- {Signal 2}
- {Signal 3}

### Neutral Factors
{List balanced or offsetting factors:}
- {Factor 1}
- {Factor 2}

---

## Strategic Recommendations

### For Current Sentiment Level ({CLASSIFICATION})

**Short-Term Positioning** (Next 1-4 weeks):
{Recommendations based on sentiment extremes or trends}

**Risk Management**:
{How to position for potential sentiment shifts}

**Opportunistic Strategies**:
{Specific strategies that work in this sentiment environment}

---

### Scenario Analysis

**If Sentiment Moves to Extreme Fear (0-24)**:
- Likelihood: {Low/Medium/High}
- Catalysts: {What could drive this}
- Positioning: {How to prepare}

**If Sentiment Moves to Extreme Greed (76-100)**:
- Likelihood: {Low/Medium/High}
- Catalysts: {What could drive this}
- Positioning: {How to prepare}

**If Sentiment Remains Neutral/Current**:
- Expected Environment: {What to expect}
- Positioning: {Appropriate strategies}

---

## What to Watch

### Sentiment Catalysts to Monitor

**Upcoming Events That Could Shift Sentiment**:
1. {Event 1: e.g., "Fed meeting on {date}"}
   - Potential Impact: {How this could affect sentiment}

2. {Event 2: e.g., "Key earnings from {sector}"}
   - Potential Impact: {How this could affect sentiment}

3. {Event 3: e.g., "Economic data: {release}"}
   - Potential Impact: {How this could affect sentiment}

**Key Indicators to Track**:
- {Indicator 1 and threshold level}
- {Indicator 2 and threshold level}
- {Indicator 3 and threshold level}

---

## Investment Strategy by Sentiment Level

### Current Strategy for {CLASSIFICATION} Sentiment

**Asset Allocation**:
- Equities: {Recommended %}
- Fixed Income: {Recommended %}
- Cash: {Recommended %}
- Alternatives: {Recommended %}

**Equity Positioning**:
- Beta Preference: {High/Low beta}
- Style: {Growth/Value/Balanced}
- Size: {Large/Mid/Small cap preference}
- Sectors: {Which sectors to favor}

**Fixed Income Positioning**:
- Duration: {Short/Intermediate/Long}
- Credit Quality: {IG/HY mix}

**Hedging Considerations**:
{Whether to hedge and how}

---

## Risk Assessment

### Current Risk Level: {Low/Moderate/High/Extreme}

**Key Risks at This Sentiment Level**:
1. {Risk 1}
   - Probability: {Low/Med/High}
   - Impact: {Low/Med/High}
   - Mitigation: {How to protect}

2. {Risk 2}
   - Probability: {Low/Med/High}
   - Impact: {Low/Med/High}
   - Mitigation: {How to protect}

3. {Risk 3}
   - Probability: {Low/Med/High}
   - Impact: {Low/Med/High}
   - Mitigation: {How to protect}

---

## Conclusion

{Final 1-2 paragraph summary:
- Recap of current sentiment score and classification
- Key takeaway for investors
- Most important factors to monitor going forward
- Overall market outlook given current sentiment}

---

## Key Takeaways

- **Sentiment Level**: {score}/100 indicates {classification} sentiment
- **Primary Drivers**: {Top 2-3 factors driving current sentiment}
- **Outlook**: {Bullish/Bearish/Neutral} with {High/Medium/Low} conviction
- **Recommended Posture**: {Aggressive/Moderate/Defensive}
- **Key Risks**: {Top 1-2 risks to monitor}
- **Opportunities**: {Top 1-2 opportunities in current environment}

---
**Disclaimer**: This analysis is for informational and educational purposes only. It does not constitute financial advice, investment recommendations, or a solicitation to buy or sell securities. Sentiment indicators are backward-looking and do not guarantee future market performance. Past performance does not guarantee future results. Consult a qualified financial advisor before making investment decisions.

---
*Data sources: {List all sources with timestamps}*
*Based on analyses from:*
- [Stock Market Analysis]({GitHub URL})
- [Investment Strategy Insights]({GitHub URL})
- [Global Market Developments]({GitHub URL})
- [Earnings & Corporate Events]({GitHub URL})

*Analysis generated: {ISO 8601 timestamp}*
