# `.claude/backup/`

Holding pen for old or pre-rewrite HTML files that used to live in `.claude/html/`.

**Why this folder exists outside `.claude/html/`:** the GitHub Pages deploy
workflow (`.github/workflows/deploy.yml`) uploads the entire `.claude/html/`
tree as the published artifact. Anything in there is reachable at
`https://edge-radar.mikesailab.com/<path>`. Keeping backups out of that
folder ensures they don't get served publicly.

## Contents

| File | What it is |
|:-----|:-----------|
| `index.html.backup-2026-05-11` | Snapshot of the old data-flow / pipeline reference page, taken just before the 2026-05-11 rewrite to the personal ops dashboard |
| `dataflow.html` | The standalone bundled "dark modern" data-flow diagram (was embedded via iframe in the pre-rewrite `index.html`). Replaced by the simple 7-step CSS strip in the new page |
| `index2.html` | An older alternate full-page variant that lived alongside `index.html` |

## Restoring

Files are plain HTML — copy whichever back into `.claude/html/` to restore, then
commit + push to master to redeploy.
