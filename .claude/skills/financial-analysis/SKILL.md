---
name: financial-analysis
description: Conduct comprehensive financial market analysis including stock market analysis, investment strategy insights, global market developments, earnings reports, and market sentiment scoring. Use when analyzing markets, researching investments, tracking earnings, or assessing market sentiment. Outputs are saved to GitHub and posted to AX MCP message board.
---

# Financial Analysis Skill

Perform comprehensive financial market analysis across 5 key analysis types, with automated GitHub publishing and team communication via AX MCP.

## Analysis Types

This skill supports 5 analysis types:

1. **Stock Market Analysis** - Daily stock exchange analysis with top movers and major stories
2. **Investment Strategy Insights** - Asset allocation, ETF performance, and risk management
3. **Global Market Developments** - International markets, central bank policies, geopolitical events
4. **Earnings & Corporate Events** - Earnings releases, corporate actions, dividend updates
5. **Market Sentiment Score** - Aggregated sentiment analysis with Fear & Greed Index scoring

## Quick Start

User can invoke this skill by asking:
- "Run stock market analysis for yesterday"
- "Generate investment strategy insights"
- "Analyze global market developments"
- "Create earnings and corporate events report"
- "Calculate market sentiment score"

## ⚠️ Git Workflow Requirements

**CRITICAL:** Before performing any git operations, read and follow the complete workflow in:
- **File:** `.claude\rules.md`
- **Location:** `D:\AI_Agents\Agent_Teams_Updated\Financial_Advisors\claude_agent_team\Financial_Advisor\.claude\rules.md`

Key requirements:
- ✅ Use local repo: `D:\AI_Agents\Repo\CommunityRepo\FinancialAdvisors\AX-CommunityWorkspaces`
- ✅ Work on `FinancialAdvisors` branch only
- ✅ Create PR to main (never push to main directly)
- ✅ All files under `financial-advisors/` folder only
- ❌ NEVER push directly to main branch
- ❌ NEVER use GitHub API for binary files

## Core Workflow

Each analysis type follows this pattern:

1. **Research & Data Collection**
   - Use web search and financial data tools to gather current market data
   - Focus on previous day's data (or current week for forward-looking analyses)
   - Cite all sources with timestamps

2. **Analysis & Report Generation**
   - Create comprehensive markdown report following the analysis type's requirements
   - Include relevant metrics, charts (if applicable), and actionable insights
   - Use professional financial analysis format

3. **GitHub Publication**
   - Use designated local repo: `D:\AI_Agents\Repo\CommunityRepo\FinancialAdvisors\AX-CommunityWorkspaces`
   - Save report to appropriate folder under `financial-advisors/`
   - Filename format: `YYYY-MM-DD-[analysis-type].md`
   - **Follow complete git workflow in `.claude\rules.md`** (sync main, rebase FinancialAdvisors branch, commit, push, create PR)

4. **Team Communication**
   - Post message to AX MCP message board
   - Include link to the GitHub page for the analysis (use FinancialAdvisors branch URL until PR is merged)
   - For Market Sentiment Score: also send team email

## Instructions by Analysis Type

### 1. Stock Market Analysis

**Scope**: Analyze the previous day's stock market performance

**Research Focus**:
- Major index performance (S&P 500, NASDAQ, DOW, Russell 2000)
- Top gaining and losing stocks
- Sector performance
- Trading volume and market breadth
- Major news stories impacting markets
- Notable technical levels or breakouts

**Report Structure**:
```markdown
# Stock Market Analysis - [Date]

## Market Overview
[Summary of overall market performance]

## Major Indices
[Performance data for key indices]

## Top Movers
### Gainers
[Top 5-10 gaining stocks with reasons]

### Losers
[Top 5-10 declining stocks with reasons]

## Sector Performance
[Sector rotation and performance analysis]

## Key Stories
[3-5 major market-moving stories]

## Technical Analysis
[Key support/resistance levels, trends]

## Outlook
[Brief forward-looking commentary]

---
*Data sources: [List sources with timestamps]*
```

**GitHub Location**: `financial-advisors/Stock-Market-Analysis/YYYY-MM-DD-stock-market-analysis.md`

**Message Board Post**: "📊 Stock Market Analysis for [Date] is now available: [GitHub link]"

---

### 2. Investment Strategy Insights

**Scope**: Comprehensive investment strategy analysis for the previous day

**Research Focus**:
- Asset allocation trends (stocks, bonds, commodities, cash)
- Top-performing ETFs across categories
- Risk management signals (VIX, put/call ratios, credit spreads)
- Sector rotation strategies
- Geographic allocation opportunities
- Yield curve and fixed income signals

**Report Structure**:
```markdown
# Investment Strategy Insights - [Date]

## Executive Summary
[Key takeaways and actionable insights]

## Asset Allocation Analysis
[Recommended allocations across asset classes]

## Top-Performing ETFs
### By Category
[Best ETFs in: Equity, Fixed Income, Commodities, International]

### Performance Leaders
[Top 10 ETFs with YTD and recent performance]

## Risk Management Signals
[VIX levels, market volatility, risk indicators]

## Sector Rotation Strategy
[Sectors to overweight/underweight and why]

## Fixed Income Insights
[Yield curve, duration strategy, credit quality]

## Geographic Allocation
[US vs International, emerging markets commentary]

## Strategic Recommendations
[3-5 key strategic moves for current environment]

---
*Data sources: [List sources with timestamps]*
```

**GitHub Location**: `financial-advisors/Investment-Strategy-Insights/YYYY-MM-DD-investment-strategy-insights.md`

**Message Board Post**: "💡 Investment Strategy Insights for [Date] is now available: [GitHub link]"

---

### 3. Global Market Developments

**Scope**: Comprehensive global market summary for the previous day

**Research Focus**:
- **European Markets**: ECB policy, key indices (DAX, FTSE, CAC), economic data
- **Asian Markets**: BOJ policy, PBOC actions, key indices (Nikkei, Hang Seng, Shanghai)
- **Central Bank Updates**: Policy stances, upcoming decision dates, rate expectations
- **Geopolitical Events**: Events with market implications
- **Currency Markets**: Major FX moves and drivers
- **Commodity Markets**: Oil, gold, key commodity trends

**Report Structure**:
```markdown
# Global Market Developments - [Date]

## Executive Summary
[Global market overview and key themes]

## European Markets
### Market Performance
[DAX, FTSE, CAC 40, Euro Stoxx 50]

### ECB Policy Update
[Current stance, upcoming decisions, rate expectations]

### Key Developments
[Economic data, political events, market drivers]

## Asian Markets
### Market Performance
[Nikkei 225, Hang Seng, Shanghai Composite, other key indices]

### Central Bank Watch
#### Bank of Japan (BOJ)
[Policy stance, yield curve control, upcoming decisions]

#### People's Bank of China (PBOC)
[Monetary policy, yuan management, stimulus measures]

### Key Developments
[Economic data, regulatory changes, market drivers]

## Geopolitical Events
[Events with market implications and impact analysis]

## Currency Markets
[Major FX moves: EUR/USD, USD/JPY, GBP/USD, USD/CNY, etc.]

## Commodity Markets
[Oil, gold, copper, agricultural commodities]

## Risk Factors
[Key risks affecting international markets]

## Calendar Watch
[Upcoming central bank meetings, economic data releases]

---
*Data sources: [List sources with timestamps]*
```

**GitHub Location**: `financial-advisors/Global-Market-Developments/YYYY-MM-DD-global-market-developments.md`

**Message Board Post**: "🌍 Global Market Developments for [Date] is now available: [GitHub link]"

---

### 4. Earnings & Corporate Events

**Scope**: Track earnings and corporate actions

**Research Focus**:
- **Upcoming Earnings**: Companies with major earnings releases in the next week
- **Recent Earnings**: Key takeaways from the week's most impactful earnings calls
- **Corporate Actions**: Notable dividends, stock splits, buyback announcements
- **M&A Activity**: Mergers, acquisitions, and strategic deals
- **Analyst Actions**: Significant upgrades, downgrades, price target changes

**Report Structure**:
```markdown
# Earnings & Corporate Events - [Date]

## Executive Summary
[Overview of earnings season and key corporate events]

## Upcoming Earnings (Next 7 Days)
[Companies reporting with expected dates, estimates, and what to watch]

### Notable Reports
| Company | Ticker | Date | Consensus EPS | Key Themes |
|---------|--------|------|---------------|------------|
| ... | ... | ... | ... | ... |

## Recent Earnings Highlights
### Major Beats
[Companies that exceeded expectations with analysis]

### Major Misses
[Companies that missed expectations with analysis]

### Key Earnings Call Takeaways
[3-5 most important insights from recent calls]

## Corporate Actions
### Dividends
[Notable dividend announcements, increases, special dividends]

### Stock Splits
[Stock split announcements and implications]

### Buybacks
[Share repurchase programs announced or expanded]

## M&A Activity
[Mergers, acquisitions, strategic deals announced]

## Analyst Actions
[Significant upgrades/downgrades from major firms]

## Sector Themes
[Common themes emerging from earnings across sectors]

## Calendar
[Detailed earnings calendar for upcoming week]

---
*Data sources: [List sources with timestamps]*
```

**GitHub Location**: `financial-advisors/Earnings-And-Corporate-Events/YYYY-MM-DD-earnings-corporate-events.md`

**Message Board Post**: "📈 Earnings & Corporate Events update for [Date] is now available: [GitHub link]"

---

### 5. Market Sentiment Score

**Scope**: Aggregate sentiment analysis based on all other financial analysis posts

**Special Instructions**: This analysis type has unique requirements:
1. **MUST read other agents' posts first** from AX MCP message board for today
2. Review the 4 analyses: Stock Market Analysis, Investment Strategy Insights, Global Market Developments, Earnings & Corporate Events
3. Calculate Market Sentiment Score using CNN Fear & Greed Index methodology (0-100)
4. **Send team email** after posting to message board

**Research Focus**:
- Synthesize findings from all 4 other analyses
- Apply CNN Fear & Greed Index framework:
  - 0-24: Extreme Fear
  - 25-44: Fear
  - 45-55: Neutral
  - 56-75: Greed
  - 76-100: Extreme Greed
- Consider: market momentum, breadth, volatility, put/call ratios, safe haven demand, junk bond demand, market breadth indicators

**Report Structure**:
```markdown
# Market Sentiment Score - [Date]

## Sentiment Score: [X]/100 - [Classification]

[Visual representation if possible, e.g., gauge or scale]

## Methodology
This score aggregates multiple sentiment indicators using the CNN Fear & Greed Index framework (0=Extreme Fear, 100=Extreme Greed).

## Component Analysis
[Break down how you arrived at the score]

### Market Momentum
[Score: X/100] - [Analysis based on Stock Market Analysis]

### Market Breadth
[Score: X/100] - [Analysis based on sector performance]

### Volatility
[Score: X/100] - [Analysis based on VIX and risk indicators]

### Safe Haven Demand
[Score: X/100] - [Analysis based on gold, bonds, flight to safety]

### Put/Call Ratios
[Score: X/100] - [Analysis based on options data]

### Junk Bond Demand
[Score: X/100] - [Analysis based on credit spreads]

### Stock Price Strength
[Score: X/100] - [Analysis based on 52-week highs/lows]

## Summary of Today's Analyses

### Stock Market Analysis
[Key findings and link to GitHub]

### Investment Strategy Insights
[Key findings and link to GitHub]

### Global Market Developments
[Key findings and link to GitHub]

### Earnings & Corporate Events
[Key findings and link to GitHub]

## Interpretation
[What this score means for investors and outlook]

## Historical Context
[Compare to recent sentiment levels if data available]

## Recommendations
[Strategic implications based on current sentiment]

---
*Data sources: [List sources with timestamps]*
*Based on analyses from: [List GitHub links to all 4 analyses]*
```

**GitHub Location**: `financial-advisors/Market-Sentiment-Score/YYYY-MM-DD-market-sentiment-score.md`

**Message Board Post**: "🎯 Market Sentiment Score for [Date]: [Score]/100 ([Classification]) - Full analysis: [GitHub link]"

**Email Requirements**:
- **Subject**: `Market Sentiment Score - [Today's Date]`
- **Recipients**:
  - Michael Schecht: michael.schecht@ax-platform.com
  - Jacob Taunton: jacob.taunton@ax-platform.com
  - Heath Dorn: heath.dorn@ax-platform.com
  - Michael Schecht (Personal): mikeschecht@gmail.com
  - Jacob Taunton (Personal): jandrewt82@gmail.com
  - Heath Dorn (Personal): Heathdorn00@yahoo.com

- **Email Body**:
```
Subject: Market Sentiment Score - [Date]

Team,

Today's Market Sentiment Score: [X]/100 - [Classification]

## Sentiment Analysis
[2-3 paragraph summary of sentiment score and reasoning]

## Summary of Today's Financial Analyses

1. Stock Market Analysis
   [Brief summary]
   Link: [GitHub URL]

2. Investment Strategy Insights
   [Brief summary]
   Link: [GitHub URL]

3. Global Market Developments
   [Brief summary]
   Link: [GitHub URL]

4. Earnings & Corporate Events
   [Brief summary]
   Link: [GitHub URL]

5. Market Sentiment Score
   [Brief summary]
   Link: [GitHub URL]

## Key Takeaways
- [Takeaway 1]
- [Takeaway 2]
- [Takeaway 3]

Best regards,
Financial Analysis Agent
```

---

## Implementation Steps

When user requests an analysis, follow these steps:

### Step 1: Identify Analysis Type
Determine which of the 5 analysis types is requested.

### Step 2: Gather Data
- Use web search tools to research market data
- For Market Sentiment Score: use AX MCP tools to read message board posts
- Cite all sources with timestamps
- Focus on previous day's data (or upcoming week for forward-looking)

### Step 3: Generate Analysis
- Create comprehensive markdown report
- Follow the report structure for that analysis type
- Include all required sections
- Add metadata (date, sources, assumptions)

### Step 4: Save to GitHub

**IMPORTANT:** Follow the complete git workflow defined in `.claude\rules.md`. Summary:

1. Navigate to designated repo: `D:\AI_Agents\Repo\CommunityRepo\FinancialAdvisors\AX-CommunityWorkspaces`
2. Sync with main branch and rebase FinancialAdvisors branch (see `.claude\rules.md` for exact commands)
3. Save file to appropriate location under `financial-advisors/[analysis-type]/YYYY-MM-DD-[analysis-type].md`
4. Commit to **FinancialAdvisors branch** (NEVER to main directly)
5. Push to origin FinancialAdvisors branch
6. Create Pull Request to main branch using GitHub tools

**Critical Rules:**
- ✅ All changes must be under `financial-advisors/` folder only
- ✅ Commit and push to `FinancialAdvisors` branch
- ✅ Create PR to main (do not merge directly)
- ❌ NEVER push directly to main
- ❌ NEVER use GitHub API for binary files (images, PDFs, charts)

See `.claude\rules.md` for complete workflow details and SSH configuration requirements.

### Step 5: Post to AX MCP Message Board
Use AX MCP tools to post message with format:
- Icon emoji specific to analysis type
- Brief description
- Link to GitHub page

### Step 6: Send Email (Market Sentiment Score Only)
Use email MCP tools to send team email with:
- Proper subject line
- All 6 recipients
- Formatted email body with sentiment score, summaries, and GitHub links

## Best Practices

1. **Data Freshness**: Always verify data is current and cite timestamps
2. **Source Attribution**: Include all data sources at end of report
3. **Objectivity**: Present balanced analysis with multiple perspectives
4. **Actionability**: Include clear implications and recommendations
5. **Consistency**: Use consistent formatting across all reports
6. **Timeliness**: Complete analysis promptly for previous day's data
7. **Git Workflow Compliance**: Follow `.claude\rules.md` exactly - use FinancialAdvisors branch, create PRs, never push to main
8. **File Location**: All files must be under `financial-advisors/` folder only
9. **Communication**: Ensure message board posts and emails are professional and concise

## Error Handling

If errors occur:
- **Git workflow issues**: Consult `.claude\rules.md` for troubleshooting, check SSH configuration, verify branch status
- **Merge conflicts**: Follow rebase conflict resolution steps in `.claude\rules.md`
- **Data unavailable**: Note gaps in report and use best available alternatives
- **Message board issues**: Retry or notify user of posting failure
- **Email issues**: Verify email MCP server is configured and retry
- **File location errors**: Ensure all changes are under `financial-advisors/` folder only

## Dependencies

- GitHub SSH credentials configured (see `.claude\rules.md` for SSH setup)
- Local git repository at: `D:\AI_Agents\Repo\CommunityRepo\FinancialAdvisors\AX-CommunityWorkspaces`
- Windows OpenSSH configured for git (see `.claude\rules.md`)
- GitHub access to create pull requests on AX-CommunityWorkspaces repo
- AX MCP server configured for message board access
- Email MCP server configured for sending team emails (Market Sentiment Score only)
- Web search and financial data tools available
- Git installed and configured locally

## Tools Typically Used

- **WebSearch**: For market research and news
- **mcp__ax-gcp__messages**: For posting to AX message board and reading posts
- **mcp__github__create_pull_request**: For creating PR from FinancialAdvisors branch to main
- **mcp__github__***: For other GitHub operations as needed
- **mcp__rube__***: For email sending (Market Sentiment Score only)
- **Bash**: For local git operations (sync, rebase, commit, push per `.claude\rules.md`)
- **Write**: For creating markdown reports locally before committing

## Notes

- All analyses are for **educational and informational purposes only**
- Not financial advice - encourage users to consult licensed professionals
- Include disclaimers in reports as appropriate
- Maintain professional tone in all communications
- Date format: YYYY-MM-DD for filenames and reports
- GitHub repo structure must match: `financial-advisors/[Analysis-Type]/[filename].md`
