"""Tests for app.domain dataclasses."""

from app.domain import Opportunity, RiskDecision, ExecutionPreview, ExecutionResult
from opportunity import Opportunity as LegacyOpportunity


class TestOpportunity:
    def test_backward_compat(self):
        """Legacy import path returns the same class."""
        assert Opportunity is LegacyOpportunity

    def test_fields(self, sample_opportunity):
        assert sample_opportunity.ticker.startswith("KX")
        assert sample_opportunity.edge > 0
        assert sample_opportunity.composite_score > 0


class TestRiskDecision:
    def test_approved(self):
        rd = RiskDecision(approved=True, approval_type="APPROVED", reason="All gates passed")
        assert rd.approved
        assert rd.timestamp  # auto-populated

    def test_rejected(self):
        rd = RiskDecision(approved=False, approval_type="REJECTED", reason="Edge below threshold")
        assert not rd.approved

    def test_capped(self):
        rd = RiskDecision(
            approved=True,
            approval_type="APPROVED_CAPPED_MAX_BET",
            reason="Downsized from $120 to $100",
            gate_results={"max_bet": "capped"},
        )
        assert rd.approved
        assert rd.gate_results["max_bet"] == "capped"


class TestExecutionPreview:
    def test_creation(self, sample_opportunity):
        rd = RiskDecision(approved=True, approval_type="APPROVED", reason="OK")
        preview = ExecutionPreview(
            opportunity=sample_opportunity,
            risk_decision=rd,
            contracts=10,
            price_cents=45,
            cost_dollars=4.50,
            bankroll_pct=0.02,
        )
        assert preview.contracts == 10
        assert preview.cost_dollars == 4.50


class TestExecutionResult:
    def test_filled(self, sample_opportunity):
        rd = RiskDecision(approved=True, approval_type="APPROVED", reason="OK")
        preview = ExecutionPreview(
            opportunity=sample_opportunity,
            risk_decision=rd,
            contracts=10,
            price_cents=45,
            cost_dollars=4.50,
            bankroll_pct=0.02,
        )
        result = ExecutionResult(
            preview=preview,
            order_id="abc-123",
            status="filled",
            filled_contracts=10,
            filled_cost=4.50,
        )
        assert result.status == "filled"
        assert result.filled_contracts == 10
        assert result.timestamp  # auto-populated
