"""Polymarket integration (Phase 1: read-only futures edge detection).

Provider #2 for Edge-Radar. Phase 1 is read-only / dry-run — it ingests
Polymarket championship-futures markets, normalizes them into the shared
``Opportunity`` object, and runs them through the existing risk gates for
preview only. Execution (wallet / py-clob-client) is Phase 2 and is NOT
implemented here. See docs/ROADMAP.md Priority 0.
"""
