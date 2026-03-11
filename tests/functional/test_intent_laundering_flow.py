"""Functional test: intent laundering prevention.

Scenario:
  A low-privilege originator (PUBLIC trust, no knowledge scopes) delegates
  to a trusted internal agent (INTERNAL trust, sip:knowledge:read scope).
  The agent tries to retrieve a document on behalf of the originator.

Expected behavior:
  - When provenance declares the originator and authority_scope is restricted
    to what the originator actually holds (nothing), the broker MUST deny the
    request with a POLICY_DENIED outcome.
  - When the agent submits a legitimate request on its own behalf (no provenance
    or provenance with full authority_scope), the broker MUST allow it.

This validates that a trusted agent cannot "launder" authority on behalf of a
principal that does not have that authority.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sip.broker.service import BrokerService
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProvenanceBlock,
    TargetDescriptor,
    TargetType,
    TrustBlock,
    TrustLevel,
)
from sip.observability.audit import ActionTaken, OutcomeSummary


def _make_envelope(
    *,
    actor_id: str,
    trust_level: TrustLevel,
    scopes: list[str],
    provenance: ProvenanceBlock | None = None,
    trust_block: TrustBlock | None = None,
) -> IntentEnvelope:
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id=actor_id,
            actor_type=ActorType.AI_AGENT,
            name="Test Agent",
            trust_level=trust_level,
            scopes=scopes,
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            parameters={"query": "architecture docs"},
        ),
        desired_outcome=DesiredOutcome(summary="Get architecture docs"),
        provenance=provenance,
        trust=trust_block or TrustBlock(declared_trust_level=trust_level),
    )


class TestIntentLaunderingPrevention:
    """End-to-end tests through the full broker pipeline."""

    # ------------------------------------------------------------------
    # Laundering denied
    # ------------------------------------------------------------------

    def test_agent_cannot_launder_on_behalf_of_low_privilege_originator(
        self, broker_no_approval: BrokerService
    ) -> None:
        """
        Low-privilege originator (PUBLIC, no scopes) delegates via an INTERNAL
        agent.  The authority_scope is restricted to what the originator holds
        (empty), so the effective scope set is empty → capability denied.
        """
        prov = ProvenanceBlock(
            originator="public-user-999",
            submitted_by="internal-agent-1",
            delegation_chain=["public-user-999", "internal-agent-1"],
            delegation_purpose="Automated retrieval on behalf of user",
            authority_scope=[],  # originator has no scopes
        )
        envelope = _make_envelope(
            actor_id="internal-agent-1",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.DENIED
        assert result.audit_record.action_taken == ActionTaken.POLICY_DENIED
        assert result.audit_record.policy_allowed is False

    def test_laundering_denied_audit_record_captures_provenance(
        self, broker_no_approval: BrokerService
    ) -> None:
        """Audit record must capture originator and delegation chain when denied."""
        prov = ProvenanceBlock(
            originator="public-user-999",
            submitted_by="internal-agent-1",
            delegation_chain=["public-user-999", "internal-agent-1"],
            authority_scope=[],
        )
        envelope = _make_envelope(
            actor_id="internal-agent-1",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.originator == "public-user-999"
        assert result.audit_record.submitting_actor == "internal-agent-1"
        assert "internal-agent-1" in result.audit_record.delegation_chain

    def test_privilege_escalation_via_trust_level_is_denied(
        self, broker_no_approval: BrokerService
    ) -> None:
        """
        Originator has PUBLIC declared trust.  The capability requires INTERNAL.
        Even if the agent (INTERNAL) has the scopes, the policy should deny
        because the originator trust is below the capability minimum.
        """
        prov = ProvenanceBlock(originator="public-originator")
        # Declare trust as PUBLIC in the trust block to simulate originator trust
        envelope = _make_envelope(
            actor_id="internal-agent-2",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
            trust_block=TrustBlock(declared_trust_level=TrustLevel.PUBLIC),
        )
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.DENIED
        assert result.audit_record.policy_allowed is False

    # ------------------------------------------------------------------
    # Legitimate flows still work
    # ------------------------------------------------------------------

    def test_agent_own_intent_without_provenance_is_allowed(
        self, broker_no_approval: BrokerService
    ) -> None:
        """Agent submits its own intent without provenance → allowed (backward compat)."""
        envelope = _make_envelope(
            actor_id="internal-agent-3",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=None,
        )
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS
        assert result.audit_record.policy_allowed is True

    def test_delegation_with_sufficient_authority_scope_is_allowed(
        self, broker_no_approval: BrokerService
    ) -> None:
        """Agent delegates with sufficient authority_scope → allowed."""
        prov = ProvenanceBlock(
            originator="privileged-user",
            submitted_by="internal-agent-4",
            delegation_chain=["privileged-user", "internal-agent-4"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = _make_envelope(
            actor_id="internal-agent-4",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS
        assert result.audit_record.policy_allowed is True

    def test_delegation_with_sufficient_authority_scope_creates_plan(
        self, broker_no_approval: BrokerService
    ) -> None:
        """Successful delegated intent produces an execution plan."""
        prov = ProvenanceBlock(
            originator="privileged-user",
            submitted_by="internal-agent-5",
            delegation_chain=["privileged-user"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = _make_envelope(
            actor_id="internal-agent-5",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        assert result.execution_plan is not None

    def test_execution_plan_carries_provenance_summary(
        self, broker_no_approval: BrokerService
    ) -> None:
        """Execution plan must carry the provenance_summary for downstream observability."""
        prov = ProvenanceBlock(
            originator="trusted-user",
            submitted_by="internal-agent-6",
            delegation_chain=["trusted-user", "internal-agent-6"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = _make_envelope(
            actor_id="internal-agent-6",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        assert result.execution_plan is not None
        summary = result.execution_plan.provenance_summary
        assert summary is not None
        assert summary["originator"] == "trusted-user"
        assert summary["submitted_by"] == "internal-agent-6"
        assert "trusted-user" in summary["delegation_chain"]

    # ------------------------------------------------------------------
    # Delegation depth at broker level
    # ------------------------------------------------------------------

    def test_excessive_delegation_chain_in_provenance_is_rejected(
        self, broker_no_approval: BrokerService
    ) -> None:
        """Delegation chain longer than 5 in provenance block → validation fail."""
        prov = ProvenanceBlock(
            originator="user-0",
            delegation_chain=["a1", "a2", "a3", "a4", "a5", "a6"],  # 6 > max 5
        )
        envelope = _make_envelope(
            actor_id="internal-agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        # Validation should catch this before policy evaluation
        assert result.audit_record.outcome_summary == OutcomeSummary.ERROR
        assert result.audit_record.action_taken == ActionTaken.VALIDATION_FAILED

    def test_expired_delegation_is_rejected_at_validation(
        self, broker_no_approval: BrokerService
    ) -> None:
        """An expired delegation_expiry → validation error."""
        prov = ProvenanceBlock(
            originator="user-0",
            delegation_expiry=datetime.now(timezone.utc) - timedelta(minutes=5),
        )
        envelope = _make_envelope(
            actor_id="internal-agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = broker_no_approval.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.ERROR
        assert result.audit_record.action_taken == ActionTaken.VALIDATION_FAILED
