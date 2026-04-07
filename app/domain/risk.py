"""
RiskDecision — the output of running an opportunity through risk gates.

Captures whether the opportunity was approved, rejected, or approved
with sizing caps applied.
"""

from dataclasses import dataclass, field
from datetime import datetime, timezone


@dataclass
class RiskDecision:
    """Result of evaluating an opportunity against the risk gate pipeline."""
    approved: bool
    approval_type: str      # APPROVED, APPROVED_CAPPED_MAX_BET, APPROVED_CAPPED_CONCENTRATION, REJECTED
    reason: str             # human-readable explanation
    gate_results: dict = field(default_factory=dict)  # gate_name -> pass/fail detail
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
