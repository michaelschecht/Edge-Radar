---
name: betting-logic-review
description: Audit Edge-Radar's betting math, risk gates, sizing, sport-specific models, and market-data handling for errors that can lose money, then save a dated findings report to docs/my-documents/repo-reviews/. Verifies every claim against the live trade log and cached odds rather than trusting docs or comments. Use for "review the betting logic", "check for betting errors", "audit the edge model", "is the sizing right", "check the sport/API data", or a periodic quant health check. Complements /repo-review, which covers structure, docs, and cruft.
argument-hint: [focus area] — e.g. "spreads", "sizing", "fees", "mlb", "polymarket", or empty for full
user-invocable: true
allowed-tools: Read, Bash, Glob, Grep, Write
---

# Betting-Logic Review

You are auditing **money-moving logic**, not code style. Every finding must be a
thing that mis-prices a market, mis-sizes a bet, bypasses a gate, or corrupts the
P&L record that calibration decisions are made from.

`$ARGUMENTS` may name a focus area (`spreads`, `sizing`, `fees`, `mlb`,
`polymarket`, `futures`, `settlement`). Emphasise it, but still run the
**Verification Battery** in full — it is cheap and it is where the real findings
come from.

## The deliverable

**Every run ends by writing a report to
`docs/my-documents/repo-reviews/YYYY-MM-DD-betting-logic-review.md`** (today's
date). This is not optional and it is not "if the user asks" — a review that
exists only in terminal scrollback is lost the moment the session ends, and the
whole point of the folder is that successive reviews can be diffed against each
other. Findings summarised in chat but never written to that file do not count
as delivered.

That folder is the running audit history; `2026-07-14-repo-review.md` (structural,
from `/repo-review`) and `2026-08-25-betting-logic-review.md` (the first pass of
this skill) are already there. **Read the most recent betting-logic report before
starting** — it tells you what was already found, what has since been fixed, and
what was explicitly ruled not-broken, so you spend the pass on new ground.

The full report format is at the bottom of this file. Write it with the Write
tool; do not commit or push.

## Ground rules

1. **Verify numerically. Never report a suspicion.** This repo's comments are
   unusually detailed and mostly accurate; the bugs that survive are the ones the
   comments are confident about. Every claim needs a number computed from
   `data/history/kalshi_trades.json`, `data/cache/odds/*.json`, or `logs/*.log`.
2. **Distinguish live from latent.** A wrong constant behind a code path nothing
   currently reaches is a *latent* finding — say so, and say what would activate it.
   Do not inflate it to Critical.
3. **Read `docs/CHANGELOG.md` before flagging a design choice.** Most of the
   surprising decisions (no correlation guard, `high` capped to `medium`, soccer
   stdev 1.8) were measured and deliberate. Re-litigating them wastes the review.
   If you disagree, cite new evidence.
4. **Cite `path:line`.** Every finding.
5. **Do not fix anything.** This is a read-and-report skill. The user decides.

## Verification Battery

Run these first. They take about two minutes and historically surface more than
reading does.

### B1 — Fee reality check

Kalshi taker fee is `ceil(0.07 × C × P × (1−P))`, rounded up **per order**. Compute
it over the settled book and compare to reported P&L and to the edge floors.

```bash
python - <<'EOF'
import json, math
d = json.load(open('data/history/kalshi_trades.json'))
s = [t for t in d if t.get('closed_at') and t.get('settlement_result') is not None]
cost = pnl = fee = 0
for t in s:
    c = int(t.get('filled_contracts') or 0); p = float(t.get('market_price_at_entry') or 0)
    if c <= 0: continue
    fee += math.ceil(0.07*c*p*(1-p)*100)/100
    cost += c*p; pnl += float(t.get('net_pnl') or 0)
print(f'settled={len(s)} stake=${cost:.2f} pnl=${pnl:.2f} ({100*pnl/cost:.1f}%)')
print(f'fees=${fee:.2f} ({100*fee/cost:.1f}% of stake)  net=${pnl-fee:.2f} ({100*(pnl-fee)/cost:.1f}%)')
EOF
```

Then check whether the fee is subtracted anywhere before a bet:
`grep -rn "fee" scripts/kalshi/kalshi_executor.py scripts/shared/`.
A fee percentage at or above `MIN_EDGE_THRESHOLD` is a **Critical** finding.

### B2 — Order health / silent failures

```bash
python - <<'EOF'
import json, collections
d = json.load(open('data/history/kalshi_trades.json'))
print(collections.Counter(t.get('status') for t in d))
print(collections.Counter(t.get('fill_status') for t in d))
for t in d[-12:]:
    print(t.get('timestamp','')[:10], t.get('status'), (t.get('error') or '')[:70])
EOF
```

Look for: `error` runs (venue rejecting orders), `unknown` status (response-shape
drift — fields the logger expects that the API stopped sending), `resting` /
`partial` clusters (limit price not reaching the book). Then confirm whether
`daily_summary.py` **reports** error rows or merely filters them — a filtered
failure is an invisible failure.

### B3 — Which books actually arrive

```bash
python - <<'EOF'
import json, glob, collections
c = collections.Counter()
for f in glob.glob('data/cache/odds/*.json'):
    try: d = json.load(open(f))
    except Exception: continue
    evs = d.get('events', d) if isinstance(d, dict) else d
    for e in (evs if isinstance(evs, list) else []):
        for b in (e.get('bookmakers') or []): c[b.get('key')] += 1
print(c.most_common(30))
EOF
```

Cross-check against `BOOK_WEIGHTS` in `edge_detector.py`. Any book with a weight
above 1.0 that never appears means the weighting scheme is inert — check the
`regions=` parameter on the Odds API call.

### B4 — Price → cents round-trip

```bash
python -c "print([c for c in range(1,100) if int(round(c/100,4)*100)!=c])"
```

Non-empty means `int(price*100)` posts limit orders below the ask at those cents.
Confirm the truncation site is the one feeding the exchange body.

### B5 — Sport coverage vs model coverage

Compare `KALSHI_TO_ODDS_SPORT` (which sports the scanner fetches) against
`_PREFIX_TO_SPORT` + `SPORT_MARGIN_STDEV` + `SPORT_TOTAL_STDEV` (which sports have
a calibrated model). Any sport in the first and not the rest silently gets the
hardcoded fallback stdev.

For each gap, check `CATEGORY_MAP` to see whether it routes to `spread`/`total`
(live risk) or only `game` (latent). Then quantify:

```bash
python - <<'EOF'
from scipy.stats import norm
for stdev, label in ((1.8,'correct'), (12.0,'fallback')):
    mean = 0.5 - stdev*norm.ppf(1-0.55)
    print(label, [round(1-norm.cdf(k, mean, stdev), 3) for k in (0.5,1.5,2.5)])
EOF
```

Also check `CATEGORY_MAP` for **prefix shadowing**: a bare series prefix that
`startswith`-matches a longer `*SPREAD` / `*TOTAL` ticker will price a spread with
moneyline fair value.

### B6 — P&L by category

```bash
python - <<'EOF'
import json, collections
d = json.load(open('data/history/kalshi_trades.json'))
agg = collections.defaultdict(lambda: [0,0.0,0.0])
for t in d:
    if t.get('settlement_result') is None: continue
    a = agg[t.get('category')]
    a[0]+=1; a[1]+=float(t.get('cost_dollars') or 0); a[2]+=float(t.get('net_pnl') or 0)
for k,(n,c,p) in sorted(agg.items()):
    print(f'{k:10s} n={n:3d} stake=${c:7.2f} pnl=${p:7.2f} roi={100*p/c if c else 0:6.1f}%')
EOF
```

A category that loses badly while others win points at *its* model, not at sizing.
Follow the losing category into its detector and price a real book by hand.

### B7 — Log signal-to-noise

```bash
grep -rho "find_market_event: [0-9]* candidate" logs/*.log | sort | uniq -c | sort -rn | head
grep -rc "WARNING" logs/*.log | sort -t: -k2 -rn | head -5
```

Thousands of benign warnings hide the real ones. Report the ratio.

### B8 — Documented rules with no code

For each **Hard Stop** and each **Gate** in `CLAUDE.md`, grep for its enforcement.
Two have historically been documentation-only (`spread > 5%`, fixed in L2 2026-08-18;
`single position > 10% of bankroll`, still open). Confirm each one actually has a
branch that can reject, and that the gate's *coverage* matches its description —
a gate that only fires on one ticker format is not the gate the table describes.

## Reading pass

After the battery, read these in order. Trace one real market end to end rather
than skimming all of them.

| Path | Look for |
|:-----|:---------|
| `scripts/kalshi/edge_detector.py` `consensus_*` | de-vig correctness; whether medians of *different quantities* come from the same book; clamps on stdev after adjustment; stale-book exclusion |
| `edge_detector.py` `detect_edge_*` | side selection before vs after adjustments; composite `min(edge/0.01, 10)` (never `edge * 20`); confidence one-way-down |
| `edge_detector.py` `find_market_event` | opponent validation, date/timezone matching, refusal on ambiguity |
| `kalshi_executor.py` `size_order` | gate order and short-circuiting; Kelly `edge/(1-price)`; `max(flat, kelly)`; caps that can still exceed their own limit via `max(1, ...)` |
| `kalshi_executor.py` `log_trade` | fields read from the API response that the response may no longer contain |
| `kalshi_settler.py` `calculate_pnl` | revenue derived per-trade not per-position; fees actually populated |
| `futures_edge.py` `devig_nway` | proportional vs power/Shin devig on N-way books; incomplete outcome lists |
| `polymarket/*_edge.py` | drift from the Kalshi composite; venue min-share handling |
| `app/config.py` vs `.env.example` vs `CLAUDE.md` | three-way drift in limits and defaults |

## Known-good — do not re-report

Established by prior review; re-report only with new contradicting evidence.

- Kelly `f* = edge / (1 - price)` (C11) is the correct binary-contract form.
- `high` confidence capped to the `medium` composite weight for sports (C4) is
  evidence-backed; futures/Polymarket deliberately keep `high: 9`.
- No correlation guard, deliberately (C11b) — measured and rejected.
- Soccer margin stdev 1.8 is calibrated against 74 World Cup matches; do not lower it.
- Fix A / Fix B cross-game contamination guards are sound.
- Per-trade (not per-position) settlement revenue is correct.

## Output

**Required.** Write to
`docs/my-documents/repo-reviews/YYYY-MM-DD-betting-logic-review.md` (today's
date). If a file for today already exists, overwrite it — one report per day, not
a pile of suffixed variants. Structure:

```markdown
# Edge-Radar Betting-Logic Review — YYYY-MM-DD

Scope + method (say that claims were verified against the trade log / odds cache,
and give the test-suite result).

## Summary
3-5 bullets, each carrying a number.

## Issues (severity-ranked)
| # | Sev | Area | Finding | Location |

Severity: Critical = money lost or lost-tracking right now.
          High = mis-prices or mis-fills on a live path.
          Medium = real defect, bounded blast radius, or latent-but-reachable.
          Low = noise, cosmetics, or a trap that needs a future change to spring.

## <one section per finding>
Mechanism, the verifying numbers, then a concrete fix with effort.

## Carried over from <date of the previous report>
Findings from the last pass that are still open, and findings that have since been
fixed (say which, and how you confirmed). A reader should be able to open only the
newest report and know the current state.

## What is *not* broken
Record what you checked and found sound, so the next pass doesn't redo it.

## Recommended order of work
| # | Action | Effort | Why in this position |

## Skipped / not reviewed
```

**Add a row to `docs/my-documents/repo-reviews/README.md`** (the folder index) for
the report you just wrote — date, link, scope, and a one-line headline. Newest
first.

When a fix later lands for a finding, annotate that finding in its original report
(`— Critical · FIXED YYYY-MM-DD`, and replace the proposed fix with what actually
shipped) rather than deleting it. The folder is a history; a finding that vanishes
loses the evidence that motivated the change.

Then print a short end-of-turn summary: counts by severity, the headline finding,
and the report's file path. **Do not commit, do not push, do not apply fixes** —
fixing is a separate request.
