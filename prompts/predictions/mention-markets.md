# TV Mention Market Scan

Scan all TV mention and word count markets for edge based on historical settlement patterns.

```
python scripts/kalshi/kalshi_executor.py status
python scripts/scan.py prediction --filter mentions --min-edge 0.05 --top 15 --exclude-open
```

Output columns: Title | Date | Cat. | Side | Mkt | Fair | Edge | Conf | Score

Show me:
- Which broadcasts have active markets tonight
- Historical YES rate for this series (what % of words typically get said?)
- Top picks where Kalshi is underpricing common words
- Any NO opportunities where Kalshi is overpricing rare/unusual words
- Quick summary: are mention markets offering good value today or should I skip them?
