# Test Commands

**Safe scan-only commands for validating updates. None include `--execute`.**

---

## 1. Sports — MLB (common flags)

```bash
python scripts/scan.py sports --filter mlb --date today --min-edge 0.05 --top 5 --exclude-open --save
```

**Tests:** `--filter`, `--date today`, `--min-edge`, `--top`, `--exclude-open`, `--save`

---

## 2. Sports — NBA (category + budget/sizing)

```bash
python scripts/scan.py sports --filter nba --category total --date tomorrow --unit-size .5 --max-bets 3 --min-bets 2 --budget 10%
```

**Tests:** `--category`, `--date tomorrow`, `--unit-size`, `--max-bets`, `--min-bets`, `--budget`

---

## 3. Sports — NHL (no date filter)

```bash
python scripts/scan.py sports --filter nhl --top 10 --exclude-open
```

**Tests:** No `--date` (all available dates), `--exclude-open`

---

## 4. Futures — NBA

```bash
python scripts/scan.py futures --filter nba-futures --top 10 --save
```

**Tests:** Futures scanner routing, `--save`

---

## 5. Prediction Markets — Crypto

```bash
python scripts/scan.py prediction --filter crypto --cross-ref --min-edge 0.05 --top 10
```

**Tests:** Prediction scanner, `--cross-ref`

---

## 6. Polymarket — Crypto

```bash
python scripts/scan.py polymarket --filter crypto --min-edge 0.05 --top 10
```

**Tests:** Polymarket scanner, cross-market edge detection
