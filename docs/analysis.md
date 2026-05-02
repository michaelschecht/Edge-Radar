# Codebase Analysis

## Overview
Edge-Radar is a Python-based automated trading system for the Kalshi prediction market platform. It scans various markets (sports, futures, and other prediction markets) for mispriced options by comparing Kalshi prices to external sources like The Odds API. It applies a set of risk management rules (gates) and uses Kelly criterion for position sizing before executing trades.

## Key Components

1. **Edge Detection (`scripts/kalshi/edge_detector.py`)**: Uses a combination of APIs (Odds API, team stats, sharp money, weather, pitcher matchup, rest days) to find an estimated fair value probability and compare it against the Kalshi market price to determine edge. Spread/total models apply a Normal distribution CDF.
2. **Risk Check / Sizing (`scripts/kalshi/risk_check.py` & `app/domain/risk.py`)**: Checks against a comprehensive set of "gates" (e.g., daily loss limit, max open positions, edge thresholds). Only opportunities that clear these gates are executed, and position size is calculated via the Kelly criterion.
3. **Configuration / Domain**: Configurations are robust (`app/config.py` and domain classes like `RiskDecision` and `Opportunity`), strongly typed via dataclasses.
4. **Testing**: Excellent test coverage (381 passed tests).
5. **Execution (`scripts/scan.py` & `scripts/kalshi/kalshi_executor.py`)**: Command line tools to preview, select, and execute trades safely.

## Recommendations & Identified Issues

### 1. Hardcoded API Endpoints and Weights
*   In `edge_detector.py`, `BOOK_WEIGHTS` is hardcoded. While helpful, it could be extracted into a configurable file or dynamic service so that if books change tier, code changes aren't required.
*   Similarly, `SPORT_MARGIN_STDEV` and `SPORT_TOTAL_STDEV` in `edge_detector.py` use empirical hardcoded values. While noted in comments that these were recently updated based on empirical review, consider externalizing these or automating their recalibration based on historical accuracy.

### 2. File caching and Global state
*   `_odds_cache` in `edge_detector.py` is a module-level dict used as a first-tier cache. This works for single processes, but if the webapp (Streamlit) or multiple concurrent scripts run, this process-level cache won't be shared. It does fall back to a file-based cache (`odds_cache.py`), but relying on global state in Python modules can sometimes lead to unexpected behaviors in long-running processes or testing environments. Ensure module state is cleared during testing or provide a clearer Cache manager class instead of module-level dicts.

### 3. API Key Rotation Logic
*   `fetch_odds_api` rotates keys on 401/429. If an API key is hit with 429, it could just be a temporary rate limit (e.g., requests per second), not exhaustion of the monthly quota. The script marks it as exhausted (`mark_exhausted`) on 401, but the rotation logic handles both 401 and 429. If 429s are temporary, rotating the key might burn through keys unnecessarily or drop valid keys. It may be better to distinguish between quota limit and rate limit (if the API supports it via headers like `X-Requests-Remaining`).

### 4. Code Duplication
*   The logic for checking `side == "yes"` vs `side == "no"` and applying signals (e.g. `pitcher_data`, `rest_data`, `sharp_money`) is duplicated across `detect_edge_game`, `detect_edge_spread`, and `detect_edge_total`. Consider extracting a helper function like `apply_confidence_signals(details, confidence, side, signals...)` to centralize this logic.

### 5. `match` statements vs `if/elif`
*   With Python 3.11+, you can leverage `match` statements for some of the complex condition chains, such as in the signal evaluations, which might improve readability.

### 6. Security
*   The `.env` and `keys/` directories are properly gitignored. Ensure that the RSA keys used for Kalshi are generated securely and perhaps suggest documentation on rotating those keys periodically.

## Conclusion
The repository is very well structured, highly modular, and well tested. The integration of caching, backtesting, and simulation showcases a mature project. The recommendations above are minor refactoring or architecture improvements to consider for long-term maintainability.
