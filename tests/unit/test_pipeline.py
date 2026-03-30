"""Tests for SIPPipeline and DecisionBundle – end-to-end pipeline tests."""

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
    Constraints,
    DataSensitivity,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProvenanceBlock,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.audit import ActionTaken, AuditRecord, OutcomeSummary
from sip.policy.interface import PolicyResult, ReasonCode
from sip.registry.bootstrap import build_seeded_registry
from sip.registry.models import CapabilityDescriptor


def _make_envelope(
    *,
    intent_name: str = "retrieve_document",
    intent_domain: str = "knowledge_management",
    operation_class: OperationClass = OperationClass.RETRIEVE,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL,
    outcome_summary: str = "Return document.",
    provenance: ProvenanceBlock | None = None,
) -> IntentEnvelope:
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="pipeline-test-actor",
            actor_type=ActorType.SERVICE,
            name="Pipeline Test",
            trust_level=trust_level,
            scopes=scopes if scopes is not None else ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary=outcome_summary),
        constraints=Constraints(data_sensitivity=data_sensitivity),
        provenance=provenance,
    )


def _get_registry_cap(capability_id: str) -> CapabilityDescriptor:
    registry = build_seeded_registry()
    return registry.get_by_id(capability_id)


class TestDecisionBundleModel:
    def test_allowed_property_true_when_plan_present(self) -> None:
        from sip.core.normalized_intent import NormalizedActor, NormalizedConstraints
        from sip.negotiation.planner import ExecutionPlan, ExecutionStep, ExecutionType, TraceMetadata
        from sip.registry.models import CapabilityDescriptor, ProviderMetadata, SchemaReference
        from uuid import uuid4

        actor = NormalizedActor(
            actor_id="a", actor_type="service", name="A", trust_level=TrustLevel.INTERNAL
        )
        ni = NormalizedIntent(
            intent_id="i",
            correlation_id="c",
            actor=actor,
            goal="g",
            constraints=NormalizedConstraints(),
            data_sensitivity=DataSensitivity.INTERNAL,
            trust_requirements=TrustLevel.INTERNAL,
            raw_request={},
        )
        cap = CapabilityDescriptor(
            capability_id="cap",
            name="Cap",
            description="d",
            provider=ProviderMetadata(provider_id="p", provider_name="P"),
            intent_domains=["t"],
            input_schema=SchemaReference(),
            output_schema=SchemaReference(),
            operation_class=OperationClass.RETRIEVE,
            minimum_trust_tier=TrustLevel.INTERNAL,
            supported_bindings=[BindingType.REST],
        )
        step = ExecutionStep(
            step_index=0,
            step_name="s",
            description="d",
            capability_id="cap",
            binding=BindingType.REST,
        )
        plan = ExecutionPlan(
            intent_id="i",
            selected_capability=cap,
            selected_binding=BindingType.REST,
            deterministic_target={"capability_id": "cap", "provider_id": "p", "binding_type": "rest", "endpoint": "e"},
            grounded_parameters={},
            execution_steps=[step],
            trace=TraceMetadata(trace_id="t", span_id="s", intent_id="i"),
        )
        from sip.observability.audit import create_audit_record, ActionTaken, OutcomeSummary
        audit = create_audit_record(
            trace_id="t",
            intent_id="i",
            actor_id="a",
            actor_type="service",
            intent_name="n",
            intent_domain="d",
            operation_class="retrieve",
            selected_capability_id="cap",
            selected_binding="rest",
            action_taken=ActionTaken.PLAN_CREATED,
            policy_allowed=True,
            outcome_summary=OutcomeSummary.SUCCESS,
        )
        bundle = DecisionBundle(
            normalized_intent=ni,
            policy_result=PolicyResult.allow(allowed_capabilities=[cap]),
            execution_plan=plan,
            audit_record=audit,
            denied=False,
        )
        assert bundle.allowed is True

    def test_allowed_property_false_when_denied(self) -> None:
        from sip.core.normalized_intent import NormalizedActor, NormalizedConstraints
        actor = NormalizedActor(
            actor_id="a", actor_type="service", name="A", trust_level=TrustLevel.INTERNAL
        )
        ni = NormalizedIntent(
            intent_id="i",
            correlation_id="c",
            actor=actor,
            goal="g",
            constraints=NormalizedConstraints(),
            data_sensitivity=DataSensitivity.INTERNAL,
            trust_requirements=TrustLevel.INTERNAL,
            raw_request={},
        )
        from sip.observability.audit import create_audit_record, ActionTaken, OutcomeSummary
        audit = create_audit_record(
            trace_id="t",
            intent_id="i",
            actor_id="a",
            actor_type="service",
            intent_name="n",
            intent_domain="d",
            operation_class="retrieve",
            selected_capability_id=None,
            selected_binding=None,
            action_taken=ActionTaken.POLICY_DENIED,
            policy_allowed=False,
            outcome_summary=OutcomeSummary.DENIED,
        )
        bundle = DecisionBundle(
            normalized_intent=ni,
            policy_result=PolicyResult.deny(
                reason_code=ReasonCode.MISSING_SCOPES, reason="missing"
            ),
            audit_record=audit,
            denied=True,
        )
        assert bundle.allowed is False


class TestSIPPipelineHappyPath:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.pipeline = SIPPipeline()

    def _get_cap(self, capability_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(capability_id)

    def test_returns_decision_bundle(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert isinstance(bundle, DecisionBundle)

    def test_allowed_bundle_has_execution_plan(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.allowed is True
        assert bundle.execution_plan is not None

    def test_bundle_has_normalized_intent(self) -> None:
        envelope = _make_envelope()
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert isinstance(bundle.normalized_intent, NormalizedIntent)
        assert bundle.normalized_intent.intent_id == envelope.intent_id

    def test_bundle_has_policy_result(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert isinstance(bundle.policy_result, PolicyResult)
        assert bundle.policy_result.allowed is True

    def test_bundle_audit_record_always_present(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert isinstance(bundle.audit_record, AuditRecord)

    def test_audit_record_populated_for_allow(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        audit = bundle.audit_record
        assert audit.policy_allowed is True
        assert audit.selected_capability_id == "retrieve_document"
        assert audit.pre_execution_denial is False
        assert audit.correlation_id == envelope.trace_id

    def test_execution_plan_has_execution_type(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.execution_plan.execution_type is not None

    def test_audit_log_accumulates(self) -> None:
        audit_log: list[AuditRecord] = []
        pipeline = SIPPipeline(audit_log=audit_log)
        cap = self._get_cap("retrieve_document")
        pipeline.process(_make_envelope(scopes=["sip:knowledge:read"]), [cap])
        pipeline.process(_make_envelope(scopes=["sip:knowledge:read"]), [cap])
        assert len(audit_log) == 2


class TestSIPPipelineDenyPath:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.pipeline = SIPPipeline()

    def _get_cap(self, capability_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(capability_id)

    def test_deny_missing_scopes(self) -> None:
        envelope = _make_envelope(scopes=[])  # no scopes
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.denied is True
        assert bundle.execution_plan is None
        assert bundle.allowed is False

    def test_audit_record_on_deny(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        audit = bundle.audit_record
        assert audit.policy_allowed is False
        assert audit.pre_execution_denial is True

    def test_deny_no_candidates(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [])  # no candidates
        assert bundle.denied is True

    def test_deny_validation_failure(self) -> None:
        """Envelope with invalid SIP version should be denied."""
        envelope = _make_envelope()
        # Use model_copy to produce an invalid version
        bad_envelope = envelope.model_copy(update={"sip_version": "99.0"})
        bundle = self.pipeline.process(bad_envelope, [self._get_cap("retrieve_document")])
        assert bundle.denied is True
        assert bundle.audit_record is not None
        assert bundle.audit_record.pre_execution_denial is True

    def test_deny_produces_audit_with_reason_code(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.audit_record.policy_reason_code is not None


class TestSIPPipelineFailClosed:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()

    def _get_cap(self, capability_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(capability_id)

    def test_fail_closed_on_missing_provenance_when_required(self) -> None:
        pipeline = SIPPipeline(require_provenance=True)
        envelope = _make_envelope(provenance=None)
        bundle = pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.denied is True
        assert bundle.policy_result.reason_code == ReasonCode.MISSING_PROVENANCE

    def test_pass_with_provenance_when_required(self) -> None:
        pipeline = SIPPipeline(require_provenance=True)
        prov = ProvenanceBlock(
            originator="orig-agent",
            submitted_by="pipeline-test-actor",
            delegation_chain=["orig-agent"],
        )
        envelope = _make_envelope(provenance=prov, scopes=["sip:knowledge:read"])
        bundle = pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.allowed is True

    def test_audit_record_always_present_on_deny(self) -> None:
        pipeline = SIPPipeline(require_provenance=True)
        envelope = _make_envelope()
        bundle = pipeline.process(envelope, [self._get_cap("retrieve_document")])
        # Even when denied, audit record is always present
        assert bundle.audit_record is not None
        assert isinstance(bundle.audit_record, AuditRecord)


class TestSIPPipelineAuditRecord:
    def setup_method(self) -> None:
        self.registry = build_seeded_registry()
        self.pipeline = SIPPipeline()

    def _get_cap(self, capability_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(capability_id)

    def test_audit_record_captures_normalized_intent_id(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.audit_record.normalized_intent_id == envelope.intent_id

    def test_audit_record_captures_expected_execution_path_on_allow(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert len(bundle.audit_record.expected_execution_path) >= 1

    def test_audit_record_has_no_execution_path_on_deny(self) -> None:
        envelope = _make_envelope(scopes=[])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.audit_record.expected_execution_path == []

    def test_audit_record_captures_selection_basis_on_allow(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.audit_record.selection_basis is not None
        assert len(bundle.audit_record.selection_basis) > 0

    def test_audit_record_captures_correlation_id(self) -> None:
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        bundle = self.pipeline.process(envelope, [self._get_cap("retrieve_document")])
        assert bundle.audit_record.correlation_id == envelope.trace_id


class TestSIPPipelineEndToEnd:
    """End-to-end pipeline integration tests."""

    def setup_method(self) -> None:
        self.registry = build_seeded_registry()

    def _get_cap(self, capability_id: str) -> CapabilityDescriptor:
        return self.registry.get_by_id(capability_id)

    def test_full_happy_path_decision_bundle(self) -> None:
        """Full pipeline: intent → normalization → policy → plan → audit."""
        audit_log: list[AuditRecord] = []
        pipeline = SIPPipeline(audit_log=audit_log)
        envelope = _make_envelope(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            scopes=["sip:knowledge:read"],
            outcome_summary="Retrieve the annual report.",
        )
        caps = [self._get_cap("retrieve_document")]
        bundle = pipeline.process(envelope, caps)

        # 1. Normalized intent
        assert bundle.normalized_intent.intent_id == envelope.intent_id
        assert bundle.normalized_intent.goal == "Retrieve the annual report."
        assert bundle.normalized_intent.actor.actor_id == "pipeline-test-actor"

        # 2. Policy decision
        assert bundle.policy_result.allowed is True
        assert bundle.policy_result.reason_code == ReasonCode.ALLOWED

        # 3. Execution plan
        assert bundle.execution_plan is not None
        assert bundle.execution_plan.selected_capability.capability_id == "retrieve_document"
        assert bundle.execution_plan.execution_type is not None
        assert len(bundle.execution_plan.execution_steps) >= 1

        # 4. Audit record
        assert bundle.audit_record.policy_allowed is True
        assert bundle.audit_record.action_taken == ActionTaken.PLAN_CREATED
        assert bundle.audit_record.outcome_summary == OutcomeSummary.SUCCESS
        assert bundle.audit_record.pre_execution_denial is False

        # Audit log populated
        assert len(audit_log) == 1

    def test_full_deny_path_decision_bundle(self) -> None:
        """Full pipeline with deny: missing scopes → denial + audit."""
        audit_log: list[AuditRecord] = []
        pipeline = SIPPipeline(audit_log=audit_log)
        envelope = _make_envelope(scopes=[])
        caps = [self._get_cap("retrieve_document")]
        bundle = pipeline.process(envelope, caps)

        assert bundle.denied is True
        assert bundle.execution_plan is None
        assert bundle.policy_result.allowed is False
        assert bundle.audit_record.policy_allowed is False
        assert bundle.audit_record.pre_execution_denial is True
        assert bundle.audit_record.action_taken == ActionTaken.POLICY_DENIED
        assert bundle.audit_record.outcome_summary == OutcomeSummary.DENIED

        assert len(audit_log) == 1

    def test_regression_existing_broker_unaffected(self) -> None:
        """Ensure existing BrokerService still works independently."""
        from sip.broker.service import BrokerService
        from sip.registry.bootstrap import build_seeded_registry

        registry_svc = build_seeded_registry()
        broker = BrokerService(registry=registry_svc)
        envelope = _make_envelope(scopes=["sip:knowledge:read"])
        result = broker.handle(envelope)
        assert result.audit_record is not None
        assert result.audit_record.intent_id == envelope.intent_id
