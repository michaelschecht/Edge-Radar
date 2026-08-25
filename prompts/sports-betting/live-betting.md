# Live (In-Progress) Game Betting

Bet on games that have **already started**. This is gated off by default — in-progress games are skipped at the risk gate (Gate 4.8) unless you explicitly opt in.

> **⚠️ Live betting is high-variance and uses fast-moving lines.** Only enable it deliberately. The model relies on bookmaker consensus that can lag the live game state.

```
python scripts/kalshi/kalshi_executor.py status

# Scan including started games (the Started/LIVE column flags them)
python scripts/scan.py sports --filter <sport> --min-edge 0.05 --top 15 --date today --save
```

To **execute** on live games, set `ALLOW_LIVE_BETS=true`. For a one-off CLI run, prepend it:

```
ALLOW_LIVE_BETS=true python scripts/scan.py sports --filter <sport> --min-edge 0.05 --max-bets 3 --unit-size 1 --date today --execute
```

If you set `ALLOW_LIVE_BETS=true` in `.env` instead, **restart any long-running host process** — gate thresholds snapshot at import time.

## Freshness guards (L1 Phase 2)

Live consensus is filtered to defend against stale lines:

- `MAX_LIVE_BOOK_AGE_SECONDS=1200` — bookmakers whose in-play line is older than 20 minutes are dropped from the live consensus.
- `MIN_LIVE_CONSENSUS_BOOKS=3` — if the staleness filter thins a started game's consensus below 3 fresh books, the game is skipped.
- `ODDS_LIVE_TTL_SECONDS=45` — the odds cache uses a much shorter TTL when a sport has an in-play event (pre-game stays at 300s).

## What to surface

- Which games on the slate are **Started/LIVE** vs pre-game
- For each live edge: Bet, Type, Pick, Edge, Conf, Score, and **how many fresh books** back the consensus
- Whether the live line looks stale (few fresh books → treat the edge with suspicion)
- A clear recommendation — live edges should clear a higher bar (5%+, high confidence) than pre-game
