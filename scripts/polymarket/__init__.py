"""Polymarket integration (Phase 1: read-only futures edge detection).

Provider #2 for Edge-Radar. Phase 1 is read-only / dry-run — it ingests
Polymarket championship-futures markets, normalizes them into the shared
``Opportunity`` object, and runs them through the existing risk gates for
preview only. Execution (Polymarket US retail API, Ed25519) is Phase 2 and is
NOT wired into the scanner here. See docs/ROADMAP.md Priority 0.
"""
