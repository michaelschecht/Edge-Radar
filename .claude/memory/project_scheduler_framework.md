---
name: project_scheduler_framework
description: Scheduler framework built 2026-03-23 — per-market independent schedulers
type: project
---

Built a scheduler framework in `scripts/schedulers/` on 2026-03-23.

**Why:** PR #14 (Jules/automated) attempted a single monolithic scheduler but had critical issues (missing KELLY_FRACTION, no DRY_RUN gate, missing apscheduler dep). Michael rejected the PR and requested a framework supporting independent per-market schedulers.

**How to apply:** Each market (NBA, crypto, MLB, etc.) gets its own scheduler profile configured via `SCHED_{NAME}_*` env vars. All schedulers default to disabled. DRY_RUN is enforced globally. Framework lives in `scripts/schedulers/`, docs in `docs/schedulers/SCHEDULER_GUIDE.md`. When activating schedulers, remind about DRY_RUN setting and have user enable specific profiles in `.env`.
