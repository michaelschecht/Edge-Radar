"""
Edge-Radar domain objects.

Typed dataclasses representing the core concepts that flow through
the scan -> risk -> execute -> settle pipeline.
"""

from app.domain.opportunity import Opportunity
from app.domain.risk import RiskDecision
from app.domain.execution import ExecutionPreview, ExecutionResult

__all__ = [
    "Opportunity",
    "RiskDecision",
    "ExecutionPreview",
    "ExecutionResult",
]
