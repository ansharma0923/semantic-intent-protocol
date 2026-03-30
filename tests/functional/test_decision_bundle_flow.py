"""Functional end-to-end tests for the canonical SIPPipeline / DecisionBundle.

These tests exercise the complete pre-execution pipeline using real registry
capabilities, covering:
- Full allow path (intent → normalization → policy → plan → audit)
- Full deny path (missing scopes → denial + audit)
- Fail-closed on missing provenance
- Fail-closed on missing approvals
- Audit log accumulation across multiple intents
- Regression: existing BrokerService unaffected
"""

from __future__ import annotations

import pytest

from sip.core.decision_bundle import DecisionBundle
from sip.core.fail_closed import FailClosedError
from sip.core.normalized_intent import NormalizedIntent
from sip.core.pipeline import SIPPipeline
from sip.core.policy_engine import CanonicalPolicyEngine
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    CapabilityRequirement,
    Constraints,
    DataSensitivity,
    DeterminismLevel,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    Priority,
    ProvenanceBlock,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.audit import ActionTaken, AuditRecord, OutcomeSummary
from sip.policy.interface import ReasonCode
from sip.registry.bootstrap import build_seeded_registry
from sip.registry.models import CapabilityDescriptor


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_envelope(
    *,
    intent_name: str = "retrieve_document",
    intent_domain: str = "knowledge_management",
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
    outcome_summary: str = "Return the requested document.",
    provenance: ProvenanceBlock | None = None,
) -> IntentEnvelope:
    if scopes is None:
        scopes = ["sip:knowledge:read"]
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="functional-test-actor",
            actor_type=ActorType.SERVICE,
            name="Functional Test Actor",
            trust_level=trust_level,
            scopes=scopes,
        ),
        target=TargetDescriptor(
            target_type=TargetType.CAPABILITY,
            target_id=intent_name,
        ),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            natural_language_hint="Functional test intent.",
            parameters={"query": "test-query"},
        ),
        desired_outcome=DesiredOutcome(summary=outcome_summary),
        constraints=Constraints(
            data_sensitivity=data_sensitivity,
            determinism_required=DeterminismLevel.STRICT,
            priority=Priority.NORMAL,
        ),
        capability_requirements=[
            CapabilityRequirement(
                capability_name=intent_name,
                required_scopes=scopes,
                preferred_binding=BindingType.REST,
                minimum_trust_tier=TrustLevel.INTERNAL,
            )
        ],
        provenance=provenance,
    )


# ---------------------------------------------------------------------------
# End-to-end allow path
# ---------------------------------------------------------------------------

class TestDecisionBundleAllowPath:
    """Full allow-path through SIPPipeline."""

    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.audit_log: list[AuditRecord] = []
        self.pipeline = SIPPipeline(audit_log=self.audit_log)

    def _cap(self, cap_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(cap_id)

    def test_returns_decision_bundle(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert isinstance(bundle, DecisionBundle)

    def test_bundle_allowed(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.allowed is True
        assert bundle.denied is False

    def test_normalized_intent_fields(self) -> None:
        """NormalizedIntent captures all critical fields from the envelope."""
        envelope = _make_envelope(outcome_summary="Fetch the monthly report.")
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        ni = bundle.normalized_intent
        assert isinstance(ni, NormalizedIntent)
        assert ni.intent_id == envelope.intent_id
        assert ni.correlation_id == envelope.trace_id
        assert ni.goal == "Fetch the monthly report."
        assert ni.actor.actor_id == "functional-test-actor"
        assert ni.schema_version == "0.2"

    def test_policy_allow_result(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.policy_result.allowed is True
        assert bundle.policy_result.reason_code == ReasonCode.ALLOWED
        assert len(bundle.policy_result.allowed_capabilities) >= 1

    def test_execution_plan_produced(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.execution_plan is not None
        ep = bundle.execution_plan
        assert ep.intent_id == envelope.intent_id
        assert ep.selected_capability.capability_id == "retrieve_document"
        assert ep.execution_type is not None
        assert len(ep.execution_steps) >= 1

    def test_audit_record_always_present(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.audit_record is not None
        assert isinstance(bundle.audit_record, AuditRecord)

    def test_audit_record_allow_fields(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        ar = bundle.audit_record
        assert ar.policy_allowed is True
        assert ar.action_taken == ActionTaken.PLAN_CREATED
        assert ar.outcome_summary == OutcomeSummary.SUCCESS
        assert ar.pre_execution_denial is False
        assert ar.intent_id == envelope.intent_id

    def test_audit_log_populated(self) -> None:
        envelope = _make_envelope()
        self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert len(self.audit_log) == 1
        assert self.audit_log[0].intent_id == envelope.intent_id

    def test_audit_record_captures_correlation_id(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.audit_record.correlation_id == envelope.trace_id

    def test_audit_record_captures_normalized_intent_id(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.audit_record.normalized_intent_id == envelope.intent_id

    def test_audit_record_has_expected_execution_path(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert len(bundle.audit_record.expected_execution_path) >= 1


# ---------------------------------------------------------------------------
# End-to-end deny path
# ---------------------------------------------------------------------------

class TestDecisionBundleDenyPath:
    """Full deny-path through SIPPipeline."""

    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.audit_log: list[AuditRecord] = []
        self.pipeline = SIPPipeline(audit_log=self.audit_log)

    def _cap(self, cap_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(cap_id)

    def test_denied_when_missing_scopes(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.denied is True
        assert bundle.allowed is False
        assert bundle.execution_plan is None

    def test_policy_deny_result(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.policy_result.allowed is False
        assert bundle.policy_result.reason_code != ReasonCode.ALLOWED

    def test_audit_record_on_deny(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        ar = bundle.audit_record
        assert ar is not None
        assert ar.policy_allowed is False
        assert ar.action_taken == ActionTaken.POLICY_DENIED
        assert ar.outcome_summary == OutcomeSummary.DENIED
        assert ar.pre_execution_denial is True

    def test_audit_record_on_deny_has_reason_code(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.audit_record.policy_reason_code is not None

    def test_audit_record_no_execution_path_on_deny(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.audit_record.expected_execution_path == []

    def test_audit_log_populated_on_deny(self) -> None:
        envelope = _make_envelope(scopes=[])
        self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert len(self.audit_log) == 1

    def test_denied_when_no_candidates(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [])
        assert bundle.denied is True

    def test_denied_when_validation_fails(self) -> None:
        """Pipeline returns denied when validation fails."""
        from unittest.mock import patch

        envelope = _make_envelope()
        with patch(
            "sip.core.pipeline.validate_envelope",
            return_value=type(
                "R",
                (),
                {"valid": False, "errors": ["forced validation error"], "warnings": []},
            )(),
        ):
            bundle = self.pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.denied is True


# ---------------------------------------------------------------------------
# Fail-closed: missing provenance
# ---------------------------------------------------------------------------

class TestFailClosedMissingProvenance:
    """K.5 – fail closed on missing provenance when required."""

    def setup_method(self) -> None:
        self.registry = build_seeded_registry()

    def _cap(self, cap_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(cap_id)

    def test_denied_when_provenance_required_and_absent(self) -> None:
        pipeline = SIPPipeline(require_provenance=True)
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.denied is True
        assert bundle.policy_result.reason_code == ReasonCode.MISSING_PROVENANCE

    def test_allowed_when_provenance_required_and_present(self) -> None:
        pipeline = SIPPipeline(require_provenance=True)
        provenance = ProvenanceBlock(
            originator="original-service",
            submitted_by="functional-test-actor",
            delegation_chain=["original-service"],
            authority_scope=["sip:knowledge:read"],
        )
        envelope = _make_envelope(
            scopes=["sip:knowledge:read"],
            provenance=provenance,
        )
        bundle = pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.allowed is True

    def test_allowed_when_provenance_not_required_and_absent(self) -> None:
        pipeline = SIPPipeline(require_provenance=False)
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.allowed is True


# ---------------------------------------------------------------------------
# Fail-closed: missing trust
# ---------------------------------------------------------------------------

class TestFailClosedMissingTrust:
    """K.6 – fail closed on missing trust."""

    def setup_method(self) -> None:
        self.registry = build_seeded_registry()

    def _cap(self, cap_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(cap_id)

    def test_denied_when_actor_trust_too_low(self) -> None:
        """PUBLIC trust → denied for INTERNAL-minimum capability."""
        pipeline = SIPPipeline()
        envelope = _make_envelope(
            trust_level=TrustLevel.PUBLIC,
            scopes=["sip:knowledge:read"],
        )
        bundle = pipeline.process(envelope, [self._cap("retrieve_document")])
        assert bundle.denied is True


# ---------------------------------------------------------------------------
# Fail-closed: missing approvals (K.7)
# ---------------------------------------------------------------------------

class TestFailClosedMissingApprovals:
    """K.7 – fail closed on missing required approvals."""

    def test_check_required_approvals_met_raises_when_missing(self) -> None:
        from sip.core.fail_closed import check_required_approvals_met, FailClosedError
        from sip.policy.interface import PolicyResult, ReasonCode

        policy = PolicyResult.allow(
            allowed_capabilities=[],
            required_approvals=["manager-1"],
        )
        with pytest.raises(FailClosedError) as exc_info:
            check_required_approvals_met(policy, provided_approvals=[])
        assert exc_info.value.denial.reason_code == ReasonCode.MISSING_REQUIRED_APPROVALS

    def test_check_required_approvals_met_passes_when_satisfied(self) -> None:
        from sip.core.fail_closed import check_required_approvals_met
        from sip.policy.interface import PolicyResult

        policy = PolicyResult.allow(
            allowed_capabilities=[],
            required_approvals=["manager-1"],
        )
        # Should not raise
        check_required_approvals_met(policy, provided_approvals=["manager-1"])

    def test_check_passes_when_no_approvals_required(self) -> None:
        from sip.core.fail_closed import check_required_approvals_met
        from sip.policy.interface import PolicyResult

        policy = PolicyResult.allow(allowed_capabilities=[])
        check_required_approvals_met(policy)  # must not raise


# ---------------------------------------------------------------------------
# Audit log accumulation
# ---------------------------------------------------------------------------

class TestAuditLogAccumulation:
    """Multiple intents produce multiple audit records in the shared log."""

    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.audit_log: list[AuditRecord] = []
        self.pipeline = SIPPipeline(audit_log=self.audit_log)

    def _cap(self, cap_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(cap_id)

    def test_audit_log_grows_with_each_intent(self) -> None:
        for _ in range(3):
            env = _make_envelope()
            self.pipeline.process(env, [self._cap("retrieve_document")])
        assert len(self.audit_log) == 3

    def test_audit_log_records_both_allow_and_deny(self) -> None:
        self.pipeline.process(
            _make_envelope(scopes=["sip:knowledge:read"]),
            [self._cap("retrieve_document")],
        )
        self.pipeline.process(
            _make_envelope(scopes=[]),
            [self._cap("retrieve_document")],
        )
        assert len(self.audit_log) == 2
        outcomes = {rec.outcome_summary for rec in self.audit_log}
        assert OutcomeSummary.SUCCESS in outcomes
        assert OutcomeSummary.DENIED in outcomes


# ---------------------------------------------------------------------------
# Regression: existing BrokerService unaffected
# ---------------------------------------------------------------------------

class TestRegressionBrokerServiceUnaffected:
    """SIPPipeline addition must not break the existing BrokerService."""

    def test_broker_service_still_works(self) -> None:
        from sip.broker.service import BrokerService

        registry = build_seeded_registry()
        broker = BrokerService(registry=registry)
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        result = broker.handle(envelope)
        assert result.audit_record is not None
        assert result.audit_record.intent_id == envelope.intent_id

    def test_broker_and_pipeline_independent_audit_logs(self) -> None:
        """BrokerService and SIPPipeline each maintain their own audit state."""
        from sip.broker.service import BrokerService

        pipeline_log: list[AuditRecord] = []
        pipeline = SIPPipeline(audit_log=pipeline_log)
        registry = build_seeded_registry()
        broker = BrokerService(registry=registry)

        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        broker.handle(envelope)
        pipeline.process(envelope, [registry.get_by_id("retrieve_document")])

        # Pipeline log has exactly one entry from the SIPPipeline call
        assert len(pipeline_log) == 1
        # Broker accumulates its own audit independently
        assert len(broker.audit_log) >= 1
