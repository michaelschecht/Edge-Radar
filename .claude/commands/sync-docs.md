---
description: Propagate new information across Edge-Radar docs, memory, changelog, skills, web-app, then commit and push
argument-hint: <information to propagate>
---

Update the following surfaces with the information provided in $ARGUMENTS. Touch only what is actually affected — skip surfaces where the information is not relevant rather than forcing edits.

**Surfaces to update (in this order):**

1. **`docs/`** — any topical doc that covers the affected area (e.g., `docs/SCRIPTS_REFERENCE.md`, `docs/ARCHITECTURE.md`, per-domain folders under `docs/kalshi-*/`, `docs/scripts/`, `docs/setup/`, `docs/web-app/`).
2. **`ROADMAP.md`** — if the information adds, completes, or reprioritizes a roadmap item.
3. **`README.md`** — only if the change affects user-visible features, commands, or setup.
4. **`CLAUDE.md`** — only if the change affects agent instructions, risk gates, env vars, project structure, or workflow.
5. **Memory** (`C:\Users\mikes\.claude\projects\D--AI-Agents-Specialized-Agents-Edge-Radar\memory\`) — update or add a memory file when the information represents durable project state, a new preference, or a non-obvious decision. Update `MEMORY.md` index. Skip if the information is ephemeral.
6. **`docs/CHANGELOG.md`** — add a dated entry summarizing the change.
7. **Edge-Radar skill** (`.claude/skills/edge-radar/SKILL.md`) — update if the change affects the unified `/edge-radar` workflow, scripts, filters, or env vars exposed via the skill.
8. **Edge-Radar Analysis skill** (locate via `Glob` for `edge-radar-analysis*` under `.claude/skills/` or user skills dir) — update if the change affects analysis workflows, calibration, snapshot charts, or backtesting.
9. **Web-app** (`webapp/`) — update only if the change affects user-facing dashboard behavior (services, views, theme, or `docs/web-app/LOCAL.md`).

**Workflow:**

- Read each candidate surface before editing to avoid duplicating or contradicting existing content.
- Batch edits in parallel where surfaces are independent.
- After edits: run `git status` and `git diff` to verify scope, then create a single commit summarizing the propagated change and `git push` to the current branch's remote.
- Follow the standard commit format (HEREDOC body, `Co-Authored-By: Claude Opus 4.7 (1M context) <noreply@anthropic.com>`).
- If any surface is intentionally skipped, mention it in the end-of-turn summary so the user can confirm.

**Information to propagate:**

$ARGUMENTS
