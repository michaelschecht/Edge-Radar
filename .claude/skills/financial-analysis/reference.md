# Financial Analysis Skill - Technical Reference

This document provides detailed technical information for the financial-analysis skill.

## GitHub Repository Structure

```
AX-CommunityWorkspaces/
└── financial-advisors/
    ├── Stock-Market-Analysis/
    │   ├── 2025-12-29-stock-market-analysis.md
    │   ├── 2025-12-30-stock-market-analysis.md
    │   └── ...
    ├── Investment-Strategy-Insights/
    │   ├── 2025-12-29-investment-strategy-insights.md
    │   └── ...
    ├── Global-Market-Developments/
    │   ├── 2025-12-29-global-market-developments.md
    │   └── ...
    ├── Earnings-And-Corporate-Events/
    │   ├── 2025-12-29-earnings-corporate-events.md
    │   └── ...
    └── Market-Sentiment-Score/
        ├── 2025-12-29-market-sentiment-score.md
        └── ...
```

## File Naming Convention

**Format**: `YYYY-MM-DD-[analysis-type-slug].md`

**Examples**:
- `2025-12-29-stock-market-analysis.md`
- `2025-12-29-investment-strategy-insights.md`
- `2025-12-29-global-market-developments.md`
- `2025-12-29-earnings-corporate-events.md`
- `2025-12-29-market-sentiment-score.md`

**Rules**:
- Always use ISO 8601 date format (YYYY-MM-DD)
- Use lowercase with hyphens for slugs
- Use `.md` extension
- Match the folder name in slug (e.g., `Stock-Market-Analysis` folder → `stock-market-analysis.md`)

## Git Workflow

### Standard Workflow (Write Access)

```bash
# Navigate to repo directory
cd /path/to/AX-CommunityWorkspaces

# Pull latest changes
git pull origin main

# Create/update analysis file
# Save to: financial-advisors/[Analysis-Type]/YYYY-MM-DD-[analysis-type].md

# Stage changes
git add financial-advisors/[Analysis-Type]/YYYY-MM-DD-[analysis-type].md

# Commit with descriptive message
git commit -m "Add [Analysis Type] for YYYY-MM-DD"

# Push to main branch
git push origin main
```

### Fallback Workflow (No Write Access)

If direct push to main fails:

```bash
# Create feature branch
git checkout -b analysis/YYYY-MM-DD-[type]

# Stage and commit
git add financial-advisors/[Analysis-Type]/YYYY-MM-DD-[analysis-type].md
git commit -m "Add [Analysis Type] for YYYY-MM-DD"

# Push branch
git push origin analysis/YYYY-MM-DD-[type]

# Create PR using GitHub CLI
gh pr create --title "Add [Analysis Type] for YYYY-MM-DD" \
  --body "Automated financial analysis for [date]" \
  --base main
```

## AX MCP Message Board Integration

### Reading Messages

Use for Market Sentiment Score to gather other analyses:

```python
# Example tool usage
mcp__ax-gcp__messages(
    action="check",
    limit=20,
    mark_read=False
)
```

Look for messages matching pattern:
- "📊 Stock Market Analysis for [Date]"
- "💡 Investment Strategy Insights for [Date]"
- "🌍 Global Market Developments for [Date]"
- "📈 Earnings & Corporate Events update for [Date]"

Extract GitHub URLs from these messages.

### Posting Messages

```python
# Example tool usage
mcp__ax-gcp__messages(
    action="send",
    content="[Emoji] [Analysis Type] for [Date] is now available: [GitHub URL]"
)
```

**Message Format Templates**:
- Stock Market: `"📊 Stock Market Analysis for {date} is now available: {github_url}"`
- Investment Strategy: `"💡 Investment Strategy Insights for {date} is now available: {github_url}"`
- Global Markets: `"🌍 Global Market Developments for {date} is now available: {github_url}"`
- Earnings: `"📈 Earnings & Corporate Events update for {date} is now available: {github_url}"`
- Sentiment: `"🎯 Market Sentiment Score for {date}: {score}/100 ({classification}) - Full analysis: {github_url}"`

## Email Integration (Market Sentiment Score Only)

### Email Configuration

**Recipients** (6 total):
```
michael.schecht@ax-platform.com
jacob.taunton@ax-platform.com
heath.dorn@ax-platform.com
mikeschecht@gmail.com
jandrewt82@gmail.com
Heathdorn00@yahoo.com
```

### Email Template

**Subject**: `Market Sentiment Score - {Date in "Month DD, YYYY" format}`

**Body Structure**:
1. Opening with sentiment score
2. 2-3 paragraph sentiment analysis
3. Summaries of all 5 analyses (including sentiment itself)
4. Each summary includes brief description and GitHub link
5. Key takeaways (3-5 bullet points)
6. Signature: "Financial Analysis Agent"

### Sending Email

Use Rube MCP tools or email MCP tools depending on configuration.

## CNN Fear & Greed Index Methodology

### Score Calculation

The Market Sentiment Score uses 7 equally-weighted components:

1. **Market Momentum** (0-100)
   - S&P 500 vs 125-day moving average
   - Higher = more greed

2. **Market Breadth** (0-100)
   - Advancing vs declining stocks on NYSE
   - New highs vs new lows
   - Higher = more greed

3. **Volatility** (0-100)
   - VIX vs 50-day average
   - Lower VIX = more greed (inverted scale)

4. **Safe Haven Demand** (0-100)
   - Stock returns vs bond returns
   - Gold performance
   - Lower safe haven demand = more greed

5. **Put/Call Ratios** (0-100)
   - CBOE put/call ratio
   - Lower ratio = more greed (inverted scale)

6. **Junk Bond Demand** (0-100)
   - High-yield spreads vs investment grade
   - Tighter spreads = more greed (inverted scale)

7. **Stock Price Strength** (0-100)
   - Number of stocks hitting 52-week highs vs lows
   - % of stocks above 50-day MA
   - Higher = more greed

### Score Interpretation

| Range | Classification | Interpretation |
|-------|---------------|----------------|
| 0-24 | Extreme Fear | Heavy selling, potential buying opportunity |
| 25-44 | Fear | Cautious sentiment, defensive positioning |
| 45-55 | Neutral | Balanced sentiment, no clear bias |
| 56-75 | Greed | Optimistic sentiment, risk-on behavior |
| 76-100 | Extreme Greed | Excessive optimism, potential reversal risk |

### Composite Calculation

```
Final Score = (Component1 + Component2 + ... + Component7) / 7
```

Round to nearest integer.

## Data Sources

### Recommended Sources

1. **Market Data**:
   - Yahoo Finance
   - MarketWatch
   - CNBC
   - Bloomberg
   - Reuters

2. **Economic Data**:
   - Federal Reserve Economic Data (FRED)
   - Bureau of Economic Analysis (BEA)
   - Bureau of Labor Statistics (BLS)

3. **Central Bank Information**:
   - Federal Reserve (federalreserve.gov)
   - European Central Bank (ecb.europa.eu)
   - Bank of Japan (boj.or.jp)
   - People's Bank of China (pbc.gov.cn)

4. **Earnings Data**:
   - Earnings Whispers
   - Yahoo Finance Earnings Calendar
   - NASDAQ Earnings Calendar
   - Company investor relations pages

5. **ETF Data**:
   - ETF.com
   - ETFdb.com
   - Morningstar
   - Fund provider websites

### Citation Format

At end of each report:
```markdown
---
*Data sources: [Source1 (timestamp)], [Source2 (timestamp)], [Source3 (timestamp)]*
*Analysis generated: [ISO 8601 timestamp]*
```

Example:
```markdown
---
*Data sources: Yahoo Finance (2025-12-29 16:00 ET), MarketWatch (2025-12-29 17:30 ET), FRED (2025-12-29)*
*Analysis generated: 2025-12-29T18:45:00-05:00*
```

## Error Handling

### GitHub Push Failures

**Scenario**: Direct push to main fails

**Solution**:
1. Create feature branch
2. Push to branch
3. Create pull request
4. Post to message board with PR link instead of main branch link
5. Notify team in message: "Note: Analysis pending PR approval"

### Message Board Access Failures

**Scenario**: Cannot post to AX MCP message board

**Solution**:
1. Complete GitHub publication
2. Log error details
3. Notify user: "Analysis published to GitHub but message board posting failed"
4. Provide GitHub URL directly to user
5. Suggest manual posting or retry

### Email Sending Failures (Market Sentiment Score)

**Scenario**: Email fails to send to team

**Solution**:
1. Complete GitHub publication and message board posting
2. Log error details
3. Notify user: "Analysis complete but email sending failed"
4. Provide formatted email text to user for manual sending
5. Suggest checking email MCP server configuration

### Data Unavailability

**Scenario**: Key data source unavailable or incomplete

**Solution**:
1. Note data gap in report: "Data for [X] unavailable as of [timestamp]"
2. Use alternative sources where possible
3. Clearly mark estimated or derived values
4. Do not fabricate data
5. Include caveat in summary section

## Quality Checklist

Before publishing any analysis, verify:

- [ ] Date is correct (previous day or specified timeframe)
- [ ] All required sections included per analysis type
- [ ] Data sources cited with timestamps
- [ ] Calculations shown for any derived metrics
- [ ] Report follows markdown structure guidelines
- [ ] File named correctly: `YYYY-MM-DD-[type].md`
- [ ] Saved to correct GitHub folder
- [ ] Git commit message is descriptive
- [ ] Successfully pushed to GitHub (or PR created)
- [ ] Message board post completed with correct format
- [ ] (Market Sentiment only) Email sent to all 6 recipients
- [ ] No unsupported claims or guarantees
- [ ] Professional tone maintained throughout
- [ ] Disclaimer included where appropriate

## MCP Tool Reference

### AX MCP Tools

**mcp__ax-gcp__messages**:
- `action="check"`: Read messages
- `action="send"`: Post message
- `limit`: Number of messages to retrieve
- `mark_read`: Mark messages as read (true/false)

### GitHub Tools

**mcp__github__create_or_update_file**:
- Create/update single files in repo
- Requires: owner, repo, path, content, message, branch

**mcp__github__push_files**:
- Push multiple files in single commit
- More efficient for batch operations

### Rube Tools (Email)

**RUBE_SEARCH_TOOLS**:
- Search for email sending tools
- Required before first email send

**RUBE_MULTI_EXECUTE_TOOL**:
- Execute email send with proper parameters
- Specify all recipients, subject, body

## Advanced Features

### Batch Processing

To run all 4 base analyses in sequence:

```
User: "Run all financial analyses for yesterday except sentiment score"
```

Agent should:
1. Run Stock Market Analysis (save, post)
2. Run Investment Strategy Insights (save, post)
3. Run Global Market Developments (save, post)
4. Run Earnings & Corporate Events (save, post)
5. Provide summary with all 4 GitHub links

Then user can request:
```
User: "Now calculate market sentiment score"
```

### Historical Comparisons

For enhanced reports, can reference previous day's or week's analyses:

```bash
# Read previous analysis
cat financial-advisors/Stock-Market-Analysis/2025-12-28-stock-market-analysis.md

# Compare key metrics
# Include in current analysis under "Historical Context" section
```

### Custom Timeframes

While default is "previous day", can adapt for:
- Weekly summaries (analyze full week)
- Month-end special reports
- Quarter-end reviews
- Custom date ranges

Adjust filename and content accordingly.

## Troubleshooting

### Issue: Skill not activating

**Symptoms**: User requests financial analysis but skill doesn't trigger

**Solutions**:
- Ensure user mentioned keywords: "stock market", "earnings", "global market", "investment", "sentiment"
- Try more explicit request: "Use the financial-analysis skill to..."
- Check that SKILL.md is in correct location: `.claude/skills/financial-analysis/SKILL.md`
- Verify YAML frontmatter is valid
- Restart Claude Code to reload skills

### Issue: GitHub authentication fails

**Symptoms**: Git push rejected or authentication required

**Solutions**:
- Check GitHub credentials are configured: `git config --list`
- Verify write access to AX-CommunityWorkspaces repo
- Try GitHub CLI authentication: `gh auth login`
- If persistent, fall back to PR creation workflow

### Issue: Cannot read other analyses (Market Sentiment)

**Symptoms**: Market Sentiment Score cannot find other analyses on message board

**Solutions**:
- Verify AX MCP server is configured correctly
- Check message board access permissions
- Confirm other analyses were posted earlier today
- Try increasing message limit in search
- Verify date format matches in message search

### Issue: Email not sending

**Symptoms**: Market Sentiment Score email fails

**Solutions**:
- Verify email MCP server configured in `.mcp.json`
- Check recipient email addresses are correct
- Ensure email server has proper authentication
- Try using alternative email tool if available
- Provide formatted email text to user for manual send

## Performance Optimization

### Parallel Operations

Where possible, parallelize:
- Web searches for different data points
- Reading multiple GitHub files
- Independent API calls

### Caching Strategy

Consider caching:
- Previous day's index closing values
- ETF performance data
- Central bank policy stances
- Earnings calendar data

Update cached data before each analysis run.

### Rate Limiting

Be mindful of:
- GitHub API rate limits (5000 requests/hour for authenticated users)
- Web scraping politeness (delay between requests)
- MCP server rate limits
- Email sending quotas

## Disclaimers

Include in reports as appropriate:

```markdown
---
**Disclaimer**: This analysis is for informational and educational purposes only. It does not constitute financial advice, investment recommendations, or a solicitation to buy or sell securities. Past performance does not guarantee future results. Consult a qualified financial advisor before making investment decisions.
```

For Market Sentiment Score email, include footer:
```
---
This analysis is provided for informational purposes only and does not constitute investment advice. Please consult with a qualified financial professional before making investment decisions.
```

## Version History

- **v1.0** (2025-12-30): Initial skill creation with all 5 analysis types
- Future: Add version notes here when updating skill

## Support

For issues with this skill:
1. Check this reference documentation
2. Review examples.md for usage patterns
3. Verify MCP server configurations in `.mcp.json`
4. Check GitHub repository access and permissions
5. Review AX MCP message board access

For feature requests or improvements:
- Document in skill directory
- Update SKILL.md with changes
- Test thoroughly before deploying
