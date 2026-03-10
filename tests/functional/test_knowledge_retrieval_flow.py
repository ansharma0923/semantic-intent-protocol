"""Functional test: enterprise knowledge retrieval flow.

Scenario: An internal service requests the latest approved architecture
document and asks for a summary of its main design decisions.

Expected behavior:
  - Matches retrieve_document or search_knowledge_base capability
  - Uses RAG or REST binding
  - No write operation (read/retrieve only)
  - No human approval required
  - Execution plan is produced
"""

from __future__ import annotations

from sip.broker.service import BrokerService
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.observability.audit import OutcomeSummary


def make_knowledge_retrieval_envelope() -> IntentEnvelope:
    """Build the knowledge retrieval intent envelope."""
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="enterprise-portal",
            actor_type=ActorType.SERVICE,
            name="Enterprise Portal",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            natural_language_hint=(
                "Get the latest approved architecture document for private "
                "service exchange and summarize the main design decisions."
            ),
            parameters={
                "query": "latest approved architecture document",
                "collection": "architecture",
                "output_format": "markdown",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Retrieve architecture document and identify main design decisions.",
            output_format="markdown",
            success_criteria=[
                "Document content is returned",
                "Design decisions are identifiable",
            ],
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.RAG),
            ProtocolBinding(binding_type=BindingType.REST),
        ],
    )


class TestKnowledgeRetrievalFlow:
    def test_flow_produces_success_outcome(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.outcome_summary == OutcomeSummary.SUCCESS

    def test_flow_selects_retrieve_document_capability(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.selected_capability_id == "retrieve_document"

    def test_flow_uses_rag_or_rest_binding(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.selected_binding in ("rag", "rest")

    def test_flow_does_not_require_approval(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.approval_required is False

    def test_flow_creates_execution_plan(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        assert result.execution_plan.intent_id == envelope.intent_id

    def test_flow_policy_is_allowed(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.policy_allowed is True

    def test_flow_produces_audit_record(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.audit_record.trace_id == envelope.trace_id
        assert result.audit_record.actor_id == "enterprise-portal"
        assert result.audit_record.intent_name == "retrieve_document"

    def test_flow_execution_plan_has_query_parameter(self, broker: BrokerService) -> None:
        envelope = make_knowledge_retrieval_envelope()
        result = broker.handle(envelope)
        assert result.execution_plan is not None
        params = result.execution_plan.grounded_parameters
        assert "query" in params
        assert "architecture" in str(params.get("query", ""))

    def test_broker_audit_log_grows(self, broker: BrokerService) -> None:
        initial_count = len(broker.audit_log)
        envelope = make_knowledge_retrieval_envelope()
        broker.handle(envelope)
        assert len(broker.audit_log) == initial_count + 1

    def test_flow_with_translation(self, broker: BrokerService) -> None:
        """Test that translate() works end-to-end and produces a RAG payload."""
        envelope = make_knowledge_retrieval_envelope()
        result, translation = broker.translate(envelope)
        assert result.execution_plan is not None
        assert translation is not None
        # RAG adapter produces collection, retrieval_query, filters, result_contract
        if translation.binding_type == BindingType.RAG:
            assert "retrieval_query" in translation.payload
            assert "collection" in translation.payload
