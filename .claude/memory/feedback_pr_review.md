---
name: feedback_pr_review
description: Standards for reviewing PRs — what to flag and reject on
type: feedback
---

Flag PRs that bypass DRY_RUN safety gates or default to live execution without explicit opt-in.

**Why:** PR #14 had a scheduler that defaulted to `--execute` with no DRY_RUN check. Michael's system runs with DRY_RUN=false in production, so an unguarded scheduler would immediately place real bets.

**How to apply:** When reviewing PRs or writing automation code, always verify: (1) DRY_RUN is checked before any execution path, (2) referenced constants/env vars actually exist, (3) new dependencies are added to requirements.txt, (4) unexplained dependencies are questioned.
