"""
ExecutionPreview / ExecutionResult — pre- and post-execution domain objects.

ExecutionPreview is what the user sees before confirming an order.
ExecutionResult is the outcome after an order has been submitted.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone

from app.domain.opportunity import Opportunity
from app.domain.risk import RiskDecision


@dataclass
class ExecutionPreview:
    """A sized order ready for user review before submission."""
    opportunity: Opportunity
    risk_decision: RiskDecision
    contracts: int
    price_cents: int
    cost_dollars: float
    bankroll_pct: float


@dataclass
class ExecutionResult:
    """The outcome of submitting an order to the exchange."""
    preview: ExecutionPreview
    order_id: str                   # exchange-assigned order ID
    status: str                     # resting, filled, partial, rejected, error
    filled_contracts: int = 0
    filled_cost: float = 0.0
    exchange_response: dict = field(default_factory=dict)
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
