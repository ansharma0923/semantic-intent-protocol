"""Unit tests for MCP adapter (additional coverage)."""

from __future__ import annotations

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
from sip.negotiation.matcher import CapabilityMatcher
from sip.negotiation.planner import ExecutionPlanner
from sip.registry.bootstrap import build_seeded_registry
from sip.translator.mcp_adapter import McpAdapter


def _make_mcp_plan(intent_name: str, intent_domain: str, scopes: list[str],
                   operation_class: OperationClass = OperationClass.RETRIEVE):
    registry = build_seeded_registry()
    matcher = CapabilityMatcher(registry)
    planner = ExecutionPlanner()
    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="mcp-test",
            actor_type=ActorType.SERVICE,
            name="MCP Test",
            trust_level=TrustLevel.INTERNAL,
            scopes=scopes,
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
        ),
        desired_outcome=DesiredOutcome(summary="MCP test"),
        protocol_bindings=[ProtocolBinding(binding_type=BindingType.MCP)],
    )
    negotiation = matcher.match(envelope)
    return planner.plan(envelope, negotiation)


class TestMcpAdapterExtended:
    def test_idempotent_in_contract(self) -> None:
        plan = _make_mcp_plan("summarize_document", "summarization", ["sip:knowledge:read"],
                              operation_class=OperationClass.ANALYZE)
        adapter = McpAdapter()
        result = adapter.translate(plan)
        contract = result.payload["execution_contract"]
        assert "idempotent" in contract

    def test_supports_dry_run_in_contract(self) -> None:
        plan = _make_mcp_plan("summarize_document", "summarization", ["sip:knowledge:read"],
                              operation_class=OperationClass.ANALYZE)
        adapter = McpAdapter()
        result = adapter.translate(plan)
        contract = result.payload["execution_contract"]
        assert "supports_dry_run" in contract

    def test_tool_arguments_include_parameters(self) -> None:
        registry = build_seeded_registry()
        matcher = CapabilityMatcher(registry)
        planner = ExecutionPlanner()
        envelope = IntentEnvelope(
            actor=ActorDescriptor(
                actor_id="mcp-test",
                actor_type=ActorType.SERVICE,
                name="MCP Test",
                trust_level=TrustLevel.INTERNAL,
                scopes=["sip:knowledge:read"],
            ),
            target=TargetDescriptor(target_type=TargetType.CAPABILITY),
            intent=IntentPayload(
                intent_name="summarize_document",
                intent_domain="summarization",
                operation_class=OperationClass.ANALYZE,
                parameters={"document_id": "doc-001"},
            ),
            desired_outcome=DesiredOutcome(summary="MCP test"),
            protocol_bindings=[ProtocolBinding(binding_type=BindingType.MCP)],
        )
        negotiation = matcher.match(envelope)
        plan = planner.plan(envelope, negotiation)
        adapter = McpAdapter()
        result = adapter.translate(plan)
        assert result.payload["tool_arguments"].get("document_id") == "doc-001"

    def test_result_repr(self) -> None:
        plan = _make_mcp_plan("summarize_document", "summarization", ["sip:knowledge:read"],
                              operation_class=OperationClass.ANALYZE)
        adapter = McpAdapter()
        result = adapter.translate(plan)
        repr_str = repr(result)
        assert "mcp" in repr_str
