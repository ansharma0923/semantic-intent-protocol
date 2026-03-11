"""Unit tests for intent provenance and delegation enforcement.

Covers:
  - ProvenanceBlock model validation
  - Delegation depth enforcement in the envelope validator
  - delegation_expiry validation in the envelope validator
  - submitted_by mismatch detection
  - authority_scope excess detection
  - Policy engine: effective-scope intersection
  - Policy engine: originator trust / privilege-escalation check
  - Backward compatibility: envelopes without provenance pass unchanged
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

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
from sip.envelope.validator import validate_envelope
from sip.negotiation.matcher import CapabilityMatcher
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import build_seeded_registry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_base_envelope(
    *,
    actor_id: str = "test-actor",
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    provenance: ProvenanceBlock | None = None,
    operation_class: OperationClass = OperationClass.RETRIEVE,
    intent_name: str = "retrieve_document",
    intent_domain: str = "knowledge_management",
) -> IntentEnvelope:
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id=actor_id,
            actor_type=ActorType.SERVICE,
            name="Test Actor",
            trust_level=trust_level,
            scopes=scopes or [],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary="Test"),
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# ProvenanceBlock model tests
# ---------------------------------------------------------------------------


class TestProvenanceBlockModel:
    def test_empty_provenance_defaults(self) -> None:
        prov = ProvenanceBlock()
        assert prov.originator is None
        assert prov.submitted_by is None
        assert prov.delegation_chain == []
        assert prov.on_behalf_of is None
        assert prov.delegation_purpose is None
        assert prov.delegation_expiry is None
        assert prov.authority_scope is None

    def test_full_provenance_construction(self) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        prov = ProvenanceBlock(
            originator="user-123",
            submitted_by="agent-456",
            delegation_chain=["user-123", "orchestrator-789"],
            on_behalf_of="user-123",
            delegation_purpose="Automated retrieval",
            delegation_expiry=expiry,
            authority_scope=["sip:knowledge:read"],
        )
        assert prov.originator == "user-123"
        assert prov.submitted_by == "agent-456"
        assert len(prov.delegation_chain) == 2
        assert prov.authority_scope == ["sip:knowledge:read"]

    def test_envelope_without_provenance_is_valid(self) -> None:
        envelope = _make_base_envelope()
        assert envelope.provenance is None
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_envelope_with_minimal_provenance_is_valid(self) -> None:
        prov = ProvenanceBlock(originator="user-1")
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Validator: delegation depth
# ---------------------------------------------------------------------------


class TestValidatorDelegationDepth:
    def test_chain_at_limit_passes(self) -> None:
        prov = ProvenanceBlock(delegation_chain=["a", "b", "c", "d", "e"])
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_chain_exceeds_limit_fails(self) -> None:
        prov = ProvenanceBlock(delegation_chain=["a", "b", "c", "d", "e", "f"])
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("delegation_chain" in e and "depth" in e for e in result.errors)

    def test_empty_chain_passes(self) -> None:
        prov = ProvenanceBlock(delegation_chain=[])
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Validator: delegation_expiry
# ---------------------------------------------------------------------------


class TestValidatorDelegationExpiry:
    def test_future_expiry_passes(self) -> None:
        expiry = datetime.now(timezone.utc) + timedelta(hours=1)
        prov = ProvenanceBlock(delegation_expiry=expiry)
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_past_expiry_fails(self) -> None:
        expiry = datetime.now(timezone.utc) - timedelta(seconds=1)
        prov = ProvenanceBlock(delegation_expiry=expiry)
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("expir" in e.lower() for e in result.errors)

    def test_no_expiry_passes(self) -> None:
        prov = ProvenanceBlock()
        envelope = _make_base_envelope(provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Validator: submitted_by mismatch
# ---------------------------------------------------------------------------


class TestValidatorSubmittedBy:
    def test_submitted_by_matching_actor_passes(self) -> None:
        prov = ProvenanceBlock(submitted_by="test-actor")
        envelope = _make_base_envelope(actor_id="test-actor", provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_submitted_by_mismatch_fails(self) -> None:
        prov = ProvenanceBlock(submitted_by="other-actor")
        envelope = _make_base_envelope(actor_id="test-actor", provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("submitted_by" in e for e in result.errors)

    def test_submitted_by_none_passes(self) -> None:
        prov = ProvenanceBlock(submitted_by=None)
        envelope = _make_base_envelope(actor_id="test-actor", provenance=prov)
        result = validate_envelope(envelope)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Validator: authority_scope restriction
# ---------------------------------------------------------------------------


class TestValidatorAuthorityScope:
    def test_authority_scope_within_actor_scopes_passes(self) -> None:
        prov = ProvenanceBlock(authority_scope=["sip:knowledge:read"])
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read", "sip:knowledge:write"],
            provenance=prov,
        )
        result = validate_envelope(envelope)
        assert result.valid is True

    def test_authority_scope_exceeds_actor_scopes_fails(self) -> None:
        prov = ProvenanceBlock(authority_scope=["sip:admin:all"])
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = validate_envelope(envelope)
        assert result.valid is False
        assert any("authority_scope" in e for e in result.errors)

    def test_authority_scope_none_passes(self) -> None:
        prov = ProvenanceBlock(authority_scope=None)
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        result = validate_envelope(envelope)
        assert result.valid is True


# ---------------------------------------------------------------------------
# Policy engine: effective scope intersection
# ---------------------------------------------------------------------------


class TestPolicyEngineEffectiveScopes:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.matcher = CapabilityMatcher(self.registry)
        self.engine = PolicyEngine(enforce_approval_policy=False)

    def test_full_actor_scopes_without_provenance_allowed(self) -> None:
        """Without provenance, actor scopes are used directly (backward compat)."""
        envelope = _make_base_envelope(scopes=["sip:knowledge:read"])
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is True

    def test_authority_scope_intersection_allows_when_sufficient(self) -> None:
        """authority_scope contains the required scope → allowed."""
        prov = ProvenanceBlock(
            originator="user-1",
            authority_scope=["sip:knowledge:read"],
        )
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read", "sip:admin:all"],
            provenance=prov,
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is True

    def test_authority_scope_intersection_denies_when_scope_missing(self) -> None:
        """authority_scope restricts: required scope excluded → denied."""
        prov = ProvenanceBlock(
            originator="user-1",
            authority_scope=["sip:other:scope"],  # does not include read
        )
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read"],  # actor has it but authority_scope excludes it
            provenance=prov,
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is False
        assert len(result.policy_decision.denied_scopes) > 0

    def test_originator_scope_restriction_prevents_privilege_escalation(self) -> None:
        """Actor has all scopes, but authority_scope is empty → no scopes available."""
        prov = ProvenanceBlock(
            originator="low-privilege-user",
            authority_scope=[],  # originator grants nothing
        )
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read"],
            provenance=prov,
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is False


# ---------------------------------------------------------------------------
# Policy engine: privilege escalation via delegation trust
# ---------------------------------------------------------------------------


class TestPolicyEngineDelegationTrust:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.matcher = CapabilityMatcher(self.registry)
        self.engine = PolicyEngine(enforce_approval_policy=False)

    def test_originator_trust_below_capability_minimum_is_denied(self) -> None:
        """Originator declared trust = PUBLIC, capability requires INTERNAL → denied."""
        prov = ProvenanceBlock(originator="public-user")
        # Envelope has trust declared as PUBLIC but actor is INTERNAL
        # We use model_copy to set declared_trust_level below the capability minimum
        base = _make_base_envelope(
            scopes=["sip:knowledge:read"],
            trust_level=TrustLevel.INTERNAL,
            provenance=prov,
        )
        envelope = base.model_copy(
            update={"trust": TrustBlock(declared_trust_level=TrustLevel.PUBLIC)}
        )
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        # retrieve_document requires INTERNAL trust; declared PUBLIC → deny
        assert result.policy_decision.allowed is False
        assert any("trust" in note.lower() for note in result.policy_decision.policy_notes)

    def test_originator_trust_meets_capability_minimum_is_allowed(self) -> None:
        """Originator declared trust = INTERNAL, capability requires INTERNAL → allowed."""
        prov = ProvenanceBlock(originator="internal-service")
        envelope = _make_base_envelope(
            scopes=["sip:knowledge:read"],
            trust_level=TrustLevel.INTERNAL,
            provenance=prov,
        )
        # declared_trust_level defaults to INTERNAL which matches actor trust_level
        negotiation = self.matcher.match(envelope)
        result = self.engine.evaluate(envelope, negotiation)
        assert result.policy_decision.allowed is True

    def test_compute_effective_scopes_with_authority_scope(self) -> None:
        """Unit-test the helper directly."""
        effective = PolicyEngine._compute_effective_scopes(
            ["sip:read", "sip:write", "sip:admin"],
            ["sip:read", "sip:write"],
        )
        assert effective == {"sip:read", "sip:write"}

    def test_compute_effective_scopes_without_authority_scope(self) -> None:
        """Without authority_scope the full actor scope set is returned."""
        effective = PolicyEngine._compute_effective_scopes(
            ["sip:read", "sip:write"],
            None,
        )
        assert effective == {"sip:read", "sip:write"}

    def test_compute_effective_scopes_empty_authority_scope(self) -> None:
        """Empty authority_scope means no scopes are delegated."""
        effective = PolicyEngine._compute_effective_scopes(
            ["sip:read", "sip:write"],
            [],
        )
        assert effective == set()


# ---------------------------------------------------------------------------
# Audit record provenance propagation
# ---------------------------------------------------------------------------


class TestAuditRecordProvenance:
    def test_audit_record_without_provenance_has_empty_defaults(self) -> None:
        from sip.observability.audit import ActionTaken, OutcomeSummary, create_audit_record

        record = create_audit_record(
            trace_id="t1",
            intent_id="i1",
            actor_id="actor1",
            actor_type="service",
            intent_name="test",
            intent_domain="test",
            operation_class="retrieve",
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.PLAN_CREATED,
            policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
        )
        assert record.originator is None
        assert record.submitting_actor is None
        assert record.delegation_chain == []

    def test_audit_record_with_provenance_fields(self) -> None:
        from sip.observability.audit import ActionTaken, OutcomeSummary, create_audit_record

        record = create_audit_record(
            trace_id="t1",
            intent_id="i1",
            actor_id="agent-1",
            actor_type="ai_agent",
            intent_name="test",
            intent_domain="test",
            operation_class="retrieve",
            selected_capability_id="cap-1",
            selected_binding="rest",
            action_taken=ActionTaken.PLAN_CREATED,
            policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
            originator="user-123",
            submitting_actor="agent-1",
            delegation_chain=["user-123", "orchestrator"],
        )
        assert record.originator == "user-123"
        assert record.submitting_actor == "agent-1"
        assert record.delegation_chain == ["user-123", "orchestrator"]


# ---------------------------------------------------------------------------
# Execution plan provenance_summary propagation
# ---------------------------------------------------------------------------


class TestExecutionPlanProvenanceSummary:
    def setup_method(self) -> None:
        from sip.negotiation.planner import ExecutionPlanner

        self.registry = build_seeded_registry()
        self.matcher = CapabilityMatcher(self.registry)
        self.engine = PolicyEngine(enforce_approval_policy=False)
        self.planner = ExecutionPlanner()

    def test_plan_without_provenance_has_none_summary(self) -> None:
        envelope = _make_base_envelope(scopes=["sip:knowledge:read"])
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.provenance_summary is None

    def test_plan_with_provenance_has_summary(self) -> None:
        prov = ProvenanceBlock(
            originator="user-1",
            submitted_by="agent-2",
            delegation_chain=["user-1", "agent-2"],
        )
        envelope = _make_base_envelope(scopes=["sip:knowledge:read"], provenance=prov)
        negotiation = self.matcher.match(envelope)
        plan = self.planner.plan(envelope, negotiation)
        assert plan.provenance_summary is not None
        assert plan.provenance_summary["originator"] == "user-1"
        assert plan.provenance_summary["submitted_by"] == "agent-2"
        assert plan.provenance_summary["delegation_chain"] == ["user-1", "agent-2"]
