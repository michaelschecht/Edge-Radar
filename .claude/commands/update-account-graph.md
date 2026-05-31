---
description: Pull the live Kalshi balance + open positions and regenerate the account-growth graph (interactive HTML + static PNG)
argument-hint: [optional --out-dir PATH] [optional --as-of YYYY-MM-DD]
---

Regenerate the Kalshi account-growth chart with current data. Both builders read settled
bets from `data/history/kalshi_settlements.json`; the live snapshot (cash, open-position
value, open-position count) is pulled live from the Kalshi API in step 1 — do **not** ask
the user for these numbers.

## Steps

1. **Pull the live snapshot** from the Kalshi API:

   ```bash
   .venv/Scripts/python.exe docs/my-documents/account-graph/Script/pull_snapshot.py
   ```

   It prints one line: `CASH=<usd> PORTFOLIO=<usd> POSITIONS=<n>`. Parse those three
   values. If the call fails (auth/network), tell the user and ask them to paste the three
   numbers from the Kalshi Portfolio Status block, then continue.

2. **Regenerate the interactive HTML** (Plotly):

   ```bash
   .venv/Scripts/python.exe docs/my-documents/account-graph/Script/build_account_graph.py \
     --cash <CASH> --portfolio <PORTFOLIO> --positions <POSITIONS> \
     --out-dir docs/my-documents/account-graph/latest
   ```

3. **Regenerate the static PNG** (matplotlib — same data, same dark theme):

   ```bash
   .venv/Scripts/python.exe docs/my-documents/account-graph/Script/build_account_png.py \
     --cash <CASH> --portfolio <PORTFOLIO> --positions <POSITIONS> \
     --out-dir docs/my-documents/account-graph/latest
   ```

   If matplotlib is missing, install it once: `.venv/Scripts/python.exe -m pip install matplotlib`.

4. **Report** the output paths and the key numbers from stdout: live total balance,
   settled-only balance, total P&L, win rate, and open-position drift.

## Notes

- This command overwrites one fixed folder — `docs/my-documents/account-graph/latest/` —
  every run, so there's always a single current graph (no per-date history). If the user
  asks to keep a dated snapshot instead, pass `$ARGUMENTS` through to override `--out-dir`
  (e.g. `--out-dir docs/my-documents/account-graph/5-31-26`) or `--as-of` (backfill).
- `--deposit` defaults to `$45.50` on `2026-03-22`. If the user mentions a new deposit, add
  `--deposit <USD>` (and `--deposit-date` if needed) to both commands.
- The HTML shows the open-position **count**; the PNG shows only the reliable cash + open
  breakdown. Keep both in sync by running them with the same args.
- If the open-position drift looks wrong (e.g. negative while the user is up overall), the
  local settlement ledger may be stale — suggest `make settle` and re-running.
