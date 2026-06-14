---
description: Propagate new information across Edge-Radar docs, memory, changelog, skills, web-app, then commit and push
argument-hint: <information to propagate>
---

Update the following surfaces with the information provided in $ARGUMENTS. Touch only what is actually affected — skip surfaces where the information is not relevant rather than forcing edits.

**Step 0 — enumerate occurrences before editing (do this first).** Identify the concrete value(s), env-var name(s), flag(s), or term(s) the change touches, then `grep`/`Grep` the whole repo (and the memory dir) for both the *old* and *new* forms. This catches drift in files not on the surface list below — and surfaces where a value was already stale before this change. Build your edit list from what the grep actually finds, not only from the checklist. Distinguish real config values from incidental matches (example `--min-edge 0.10` invocations, price-bucket tables, CSS opacity like `0.08`) and leave those alone.

**Surfaces to update (in this order):**

1. **`docs/`** — any topical doc that covers the affected area (e.g., `docs/SCRIPTS_REFERENCE.md`, `docs/ARCHITECTURE.md`, per-domain folders under `docs/kalshi-*/`, `docs/scripts/`, `docs/setup/`, `docs/web-app/`).
2. **`.env.example` + `CLAUDE.md`** — for any env-var / risk-gate / config-default change, these are primary surfaces and the most prone to drift. `.env.example` is the tracked config template (values + their inline rationale comments); `CLAUDE.md` covers agent instructions, risk gates, env vars, project structure, and workflow. Update both whenever a knob, default, or gate changes.
3. **`ROADMAP.md`** — if the information adds, completes, or reprioritizes a roadmap item.
4. **`README.md`** — only if the change affects user-visible features, commands, or setup.
5. **Memory** (`C:\Users\mikes\.claude\projects\D--AI-Agents-Specialized-Agents-Edge-Radar\memory\`) — update or add a memory file when the information represents durable project state, a new preference, or a non-obvious decision. Update `MEMORY.md` index (including the one-line hook if it quotes a now-changed value). Skip if the information is ephemeral.
6. **`docs/CHANGELOG.md`** — add a dated entry summarizing the change. Leave prior dated entries intact as historical record — never rewrite history; add a new entry instead.
7. **Edge-Radar skill** (`Skills/edge-radar/SKILL.md` — canonical source; `.claude/skills/edge-radar/` is a git-ignored junction to it) — update if the change affects the unified `/edge-radar` workflow, scripts, filters, or env vars exposed via the skill.
8. **Edge-Radar Analysis skill** (`Skills/edge-radar-analysis/SKILL.md` — canonical source; edit there, not the `.claude/skills/` junction) — update if the change affects analysis workflows, calibration, snapshot charts, or backtesting.
9. **Web-app** (`webapp/`) — update if the change affects user-facing dashboard behavior (services, views, theme, or `docs/web-app/LOCAL.md`) **or** any hardcoded help text, tooltips, labels, or captions that quote a config value/default (most webapp threshold logic reads from `.env` via `app.config`, so these strings are usually the only thing that drifts).
10. **Public site** (`.claude/html/`) — update only if the change is reflected in user-facing copy on the published Pages site. The account-graph data file is generated — never hand-edit it.

**Workflow:**

- Read each candidate surface before editing to avoid duplicating or contradicting existing content.
- Batch edits in parallel where surfaces are independent.
- After edits: re-run the Step 0 grep for the *old* form to confirm no stray occurrences remain, then run `git status` and `git diff` to verify scope, create a single commit summarizing the propagated change, and `git push` to the current branch's remote.
- Follow the repo's standard commit convention, including whatever `Co-Authored-By:` trailer the harness specifies for the current model (do not hardcode a model version here).
- If any surface is intentionally skipped, mention it in the end-of-turn summary so the user can confirm.

**Information to propagate:**

$ARGUMENTS
