---
description: Audit the entire Edge-Radar repo for issues, inconsistencies, recommended updates, enhancements, and removable cruft; save findings to docs/my-documents/repo-reviews/
argument-hint: [optional focus area or 'full']
---

Conduct a thorough top-to-bottom review of the Edge-Radar repo. Read enough to form grounded judgments — don't just skim filenames.

**Scope (cover all of these):**

- `scripts/` — entry points, kalshi/, shared/, schedulers/, backtest/
- `.claude/` — agents, skills, commands, memory references
- `app/` — config, domain dataclasses
- `docs/` — every subdirectory; check for staleness, contradictions, broken links
- `tests/` — coverage gaps, skipped tests, flaky patterns, fixtures
- `webapp/` — views, services, theme, deployment docs
- Top-level files — `CLAUDE.md`, `ROADMAP.md`, `README.md`, `Makefile`, `.env.example`, `.pre-commit-config.yaml`, `requirements.txt`

If $ARGUMENTS specifies a focus area (e.g., `webapp`, `risk gates`, `tests`), emphasize that area but still note critical issues anywhere else.

**What to look for:**

1. **Issues** — bugs, security risks (hardcoded secrets, missing `.env` loads, log leakage), broken imports, dead code paths, missing error handling at system boundaries, race conditions, risk-gate bypasses.
2. **Inconsistencies** — env vars referenced in code but not in `.env.example` (or vice versa); docs that contradict code (e.g., `CLAUDE.md` risk-gate numbers vs. actual `risk_check.py` behavior); duplicate logic across `scripts/` and `webapp/services.py`; agent definitions that don't match current workflow.
3. **Recommended updates** — outdated docs, stale memory references, deprecated patterns, missing test coverage on recent changes (check `git log` for recent commits without corresponding test edits).
4. **Enhancements** — concrete suggestions only (with rough effort estimate: small/medium/large). No vague "consider adding observability" — say what, where, and why.
5. **Removable cruft** — orphaned scripts, dead files, gitignored directories that should be deleted from disk, unused dependencies in `requirements.txt`, agent definitions or skills that no longer reflect reality, obsolete docs in `docs/my-documents/temp/` or `docs/enhancements/`.

**Workflow:**

- Start by reading `CLAUDE.md`, `ROADMAP.md`, `README.md`, and `docs/CHANGELOG.md` to ground yourself in current project state.
- Use parallel `Glob`/`Grep`/`Read` calls to cover ground efficiently.
- Spot-check claims by reading the actual source — don't trust docs alone.
- Cross-reference: env vars in `.env.example` vs. `os.getenv` calls vs. `app/config.py` vs. `CLAUDE.md` risk-limits table.
- For each finding, cite specific files with `path:line` references so the user can jump to the source.

**Output:**

Save findings to `docs/my-documents/repo-reviews/YYYY-MM-DD-repo-review.md` (use today's date). Use proper markdown — H2 sections, tables where they help, code blocks for snippets. Structure:

```markdown
# Edge-Radar Repo Review — YYYY-MM-DD

## Summary
3-5 bullets: headline findings and overall health.

## Issues (severity-ranked)
| # | Severity | Area | Finding | Location |
|---|----------|------|---------|----------|
| 1 | High | risk-gates | ... | `scripts/kalshi/risk_check.py:142` |

## Inconsistencies
...

## Recommended Updates
...

## Enhancement Proposals
| Idea | Why | Effort | Where |
|------|-----|--------|-------|
...

## Removable Cruft
...

## Skipped / Not Reviewed
Anything intentionally out of scope.
```

After saving, print a brief end-of-turn summary: report count by category and the output file path. Do not commit or push — leave that to the user.
