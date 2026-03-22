"""
probability.py
Shared probability math for prediction market edge detection.

Provides strike-probability calculations for financial assets (crypto, equities)
and weather forecasts using normal distribution models.
"""

import math
from scipy.stats import norm


def strike_probability(
    current_price: float,
    strike: float,
    annual_volatility: float,
    hours_to_expiry: float,
    drift: float = 0.0,
) -> float:
    """
    Probability that price will be ABOVE strike at expiry.

    Uses geometric Brownian motion (log-normal) model:
        ln(S_T) ~ N(ln(S_0) + (mu - vol^2/2)*t, vol^2 * t)

    Args:
        current_price: Current asset price
        strike: Strike/threshold price
        annual_volatility: Annualized volatility (e.g., 0.60 for 60%)
        hours_to_expiry: Hours until settlement
        drift: Annualized drift (default 0 for short horizons)

    Returns:
        Probability between 0 and 1 that price > strike at expiry
    """
    if current_price <= 0 or strike <= 0 or hours_to_expiry <= 0:
        return 0.5
    if annual_volatility <= 0:
        return 1.0 if current_price > strike else 0.0

    t = hours_to_expiry / 8760  # hours to years
    vol_t = annual_volatility * math.sqrt(t)

    if vol_t < 1e-10:
        return 1.0 if current_price > strike else 0.0

    d = (math.log(current_price / strike) + (drift - 0.5 * annual_volatility**2) * t) / vol_t

    return float(norm.cdf(d))


def weather_probability(
    forecast_temp: float,
    strike: float,
    uncertainty: float = 3.0,
) -> float:
    """
    Probability that actual temperature will be ABOVE strike.

    Uses a simple normal model around the NWS forecast, where uncertainty
    increases with forecast horizon.

    Args:
        forecast_temp: NWS forecast high temperature (°F)
        strike: Temperature threshold from Kalshi market
        uncertainty: Standard deviation of forecast error (°F).
                     Typically 3°F for day 1, 4°F for day 2, 5°F for day 3.

    Returns:
        Probability between 0 and 1 that actual temp > strike
    """
    if uncertainty <= 0:
        return 1.0 if forecast_temp > strike else 0.0

    z = (strike - forecast_temp) / uncertainty
    return float(1.0 - norm.cdf(z))


def realized_volatility(prices: list[float]) -> float:
    """
    Compute annualized realized volatility from a price series.

    Args:
        prices: List of prices (e.g., hourly). Must have at least 2 values.

    Returns:
        Annualized volatility (e.g., 0.60 for 60% annual vol)
    """
    if len(prices) < 2:
        return 0.0

    log_returns = [
        math.log(prices[i] / prices[i - 1])
        for i in range(1, len(prices))
        if prices[i] > 0 and prices[i - 1] > 0
    ]

    if len(log_returns) < 2:
        return 0.0

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / (len(log_returns) - 1)
    hourly_vol = math.sqrt(variance)

    # Annualize: assume hourly data, 8760 hours/year
    return hourly_vol * math.sqrt(8760)
