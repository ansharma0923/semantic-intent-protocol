"""Unit tests for the REST and MCP translator adapters."""

from __future__ import annotations

import pytest

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
from sip.translator.a2a_adapter import A2aAdapter
from sip.translator.grpc_adapter import GrpcAdapter
from sip.translator.mcp_adapter import McpAdapter
from sip.translator.rag_adapter import RagAdapter
from sip.translator.rest_adapter import RestAdapter


def _make_plan(
    intent_name: str,
    intent_domain: str,
    operation_class: OperationClass,
    preferred_binding: BindingType,
    scopes: list[str] | None = None,
    parameters: dict | None = None,
    trust_level: TrustLevel = TrustLevel.INTERNAL,
):
    registry = build_seeded_registry()
    matcher = CapabilityMatcher(registry)
    planner = ExecutionPlanner()

    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="adapter-test",
            actor_type=ActorType.SERVICE,
            name="Adapter Test",
            trust_level=trust_level,
            scopes=scopes or ["sip:knowledge:read"],
        ),
        target=TargetDescriptor(target_type=TargetType.CAPABILITY),
        intent=IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=operation_class,
            parameters=parameters or {},
        ),
        desired_outcome=DesiredOutcome(summary="Test"),
        protocol_bindings=[ProtocolBinding(binding_type=preferred_binding)],
    )
    negotiation = matcher.match(envelope)
    return planner.plan(envelope, negotiation)


class TestRestAdapter:
    def test_translate_read_produces_get(self) -> None:
        plan = _make_plan(
            "retrieve_document", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.REST,
        )
        adapter = RestAdapter()
        result = adapter.translate(plan)
        assert result.payload["method"] == "GET"

    def test_translate_write_produces_post(self) -> None:
        plan = _make_plan(
            "reserve_table", "booking",
            OperationClass.WRITE, BindingType.REST,
            scopes=["sip:booking:write"],
        )
        adapter = RestAdapter()
        result = adapter.translate(plan)
        assert result.payload["method"] == "POST"

    def test_translate_has_required_fields(self) -> None:
        plan = _make_plan(
            "retrieve_document", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.REST,
        )
        adapter = RestAdapter()
        result = adapter.translate(plan)
        for field in ("method", "path", "headers", "body", "query_params"):
            assert field in result.payload

    def test_translate_has_sip_trace_headers(self) -> None:
        plan = _make_plan(
            "retrieve_document", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.REST,
        )
        adapter = RestAdapter()
        result = adapter.translate(plan)
        headers = result.payload["headers"]
        assert "X-SIP-Trace-Id" in headers
        assert "X-SIP-Intent-Id" in headers

    def test_wrong_binding_raises(self) -> None:
        plan = _make_plan(
            "retrieve_document", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.RAG,
        )
        adapter = RestAdapter()
        with pytest.raises(ValueError):
            adapter.translate(plan)

    def test_binding_type_is_rest(self) -> None:
        assert RestAdapter().binding_type == BindingType.REST

    def test_path_derived_from_capability_id(self) -> None:
        plan = _make_plan(
            "retrieve_document", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.REST,
        )
        adapter = RestAdapter()
        result = adapter.translate(plan)
        assert "retrieve-document" in result.payload["path"]


class TestMcpAdapter:
    def test_translate_has_required_fields(self) -> None:
        plan = _make_plan(
            "summarize_document", "summarization",
            OperationClass.ANALYZE, BindingType.MCP,
        )
        adapter = McpAdapter()
        result = adapter.translate(plan)
        for field in ("tool_name", "tool_arguments", "execution_contract"):
            assert field in result.payload

    def test_tool_name_matches_capability(self) -> None:
        plan = _make_plan(
            "summarize_document", "summarization",
            OperationClass.ANALYZE, BindingType.MCP,
        )
        adapter = McpAdapter()
        result = adapter.translate(plan)
        assert result.payload["tool_name"] == "summarize_document"

    def test_execution_contract_has_schema(self) -> None:
        plan = _make_plan(
            "summarize_document", "summarization",
            OperationClass.ANALYZE, BindingType.MCP,
        )
        adapter = McpAdapter()
        result = adapter.translate(plan)
        contract = result.payload["execution_contract"]
        assert "input_schema" in contract
        assert "output_schema" in contract

    def test_trace_is_included(self) -> None:
        plan = _make_plan(
            "summarize_document", "summarization",
            OperationClass.ANALYZE, BindingType.MCP,
        )
        adapter = McpAdapter()
        result = adapter.translate(plan)
        assert "trace" in result.payload
        assert result.payload["trace"]["trace_id"] == plan.trace.trace_id

    def test_binding_type_is_mcp(self) -> None:
        assert McpAdapter().binding_type == BindingType.MCP


class TestGrpcAdapter:
    def test_translate_has_required_fields(self) -> None:
        plan = _make_plan(
            "diagnose_network_issue", "network_operations",
            OperationClass.ANALYZE, BindingType.GRPC,
            scopes=["sip:network:read"],
        )
        adapter = GrpcAdapter()
        result = adapter.translate(plan)
        for field in ("service_name", "method_name", "request_message"):
            assert field in result.payload

    def test_service_name_is_qualified(self) -> None:
        plan = _make_plan(
            "diagnose_network_issue", "network_operations",
            OperationClass.ANALYZE, BindingType.GRPC,
            scopes=["sip:network:read"],
        )
        adapter = GrpcAdapter()
        result = adapter.translate(plan)
        assert "." in result.payload["service_name"]

    def test_binding_type_is_grpc(self) -> None:
        assert GrpcAdapter().binding_type == BindingType.GRPC


class TestA2aAdapter:
    def test_translate_has_required_fields(self) -> None:
        plan = _make_plan(
            "collect_device_telemetry", "network_operations",
            OperationClass.READ, BindingType.A2A,
            scopes=["sip:network:read"],
        )
        adapter = A2aAdapter()
        result = adapter.translate(plan)
        for field in ("agent_task_type", "target_agent", "task_payload", "delegation_context"):
            assert field in result.payload

    def test_binding_type_is_a2a(self) -> None:
        assert A2aAdapter().binding_type == BindingType.A2A


class TestRagAdapter:
    def test_translate_has_required_fields(self) -> None:
        plan = _make_plan(
            "search_knowledge_base", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.RAG,
            parameters={"query": "architecture decisions"},
        )
        adapter = RagAdapter()
        result = adapter.translate(plan)
        for field in ("collection", "retrieval_query", "filters", "result_contract"):
            assert field in result.payload

    def test_retrieval_query_uses_query_param(self) -> None:
        plan = _make_plan(
            "search_knowledge_base", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.RAG,
            parameters={"query": "main design decisions"},
        )
        adapter = RagAdapter()
        result = adapter.translate(plan)
        assert result.payload["retrieval_query"] == "main design decisions"

    def test_binding_type_is_rag(self) -> None:
        assert RagAdapter().binding_type == BindingType.RAG

    def test_rag_raises_when_no_query_param(self) -> None:
        """RAG adapter must refuse to produce a vague query — determinism principle."""
        from uuid import uuid4

        from sip.negotiation.planner import ExecutionPlan, ExecutionStep, TraceMetadata
        from sip.registry.bootstrap import build_seeded_registry

        registry = build_seeded_registry()
        cap = registry.get_by_id("search_knowledge_base")
        assert cap is not None

        plan = ExecutionPlan(
            intent_id=str(uuid4()),
            selected_capability=cap,
            selected_binding=BindingType.RAG,
            deterministic_target={
                "capability_id": cap.capability_id,
                "provider_id": cap.provider.provider_id,
                "binding_type": "rag",
                "endpoint": None,
            },
            grounded_parameters={},  # deliberately empty — no query
            execution_steps=[
                ExecutionStep(
                    step_index=0,
                    step_name="invoke_search",
                    description="test",
                    capability_id=cap.capability_id,
                    binding=BindingType.RAG,
                    parameters={},
                )
            ],
            trace=TraceMetadata(
                trace_id=str(uuid4()),
                span_id=str(uuid4()),
                intent_id=str(uuid4()),
            ),
        )
        adapter = RagAdapter()
        with pytest.raises(ValueError, match="deterministic retrieval query"):
            adapter.translate(plan)

    def test_rag_uses_text_param_fallback(self) -> None:
        # retrieve_document has no required fields, so 'text' param will be used
        plan = _make_plan(
            "retrieve_document", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.RAG,
            parameters={"text": "design patterns"},
        )
        adapter = RagAdapter()
        result = adapter.translate(plan)
        assert result.payload["retrieval_query"] == "design patterns"

    def test_rag_trace_present(self) -> None:
        plan = _make_plan(
            "search_knowledge_base", "knowledge_management",
            OperationClass.RETRIEVE, BindingType.RAG,
            parameters={"query": "test"},
        )
        adapter = RagAdapter()
        result = adapter.translate(plan)
        assert "trace" in result.payload
        assert "trace_id" in result.payload["trace"]
        assert "intent_id" in result.payload["trace"]


class TestGrpcAdapterExtended:
    def test_service_name_is_namespaced(self) -> None:
        """gRPC service name must be of the form sip.<provider>.<Service>Service."""
        plan = _make_plan(
            "diagnose_network_issue", "network_operations",
            OperationClass.ANALYZE, BindingType.GRPC,
            scopes=["sip:network:read"],
        )
        adapter = GrpcAdapter()
        result = adapter.translate(plan)
        service = result.payload["service_name"]
        assert service.startswith("sip.")
        assert service.endswith("Service")

    def test_method_name_is_pascal_case(self) -> None:
        plan = _make_plan(
            "diagnose_network_issue", "network_operations",
            OperationClass.ANALYZE, BindingType.GRPC,
            scopes=["sip:network:read"],
        )
        adapter = GrpcAdapter()
        result = adapter.translate(plan)
        method = result.payload["method_name"]
        assert method[0].isupper(), f"Expected PascalCase method, got '{method}'"
        assert "_" not in method

    def test_grpc_metadata_contains_trace_ids(self) -> None:
        plan = _make_plan(
            "diagnose_network_issue", "network_operations",
            OperationClass.ANALYZE, BindingType.GRPC,
            scopes=["sip:network:read"],
        )
        adapter = GrpcAdapter()
        result = adapter.translate(plan)
        metadata_keys = [k for k, _ in result.payload["grpc_metadata"]]
        assert "x-sip-trace-id" in metadata_keys
        assert "x-sip-span-id" in metadata_keys
        assert "x-sip-intent-id" in metadata_keys

    def test_request_message_contains_parameters(self) -> None:
        plan = _make_plan(
            "diagnose_network_issue", "network_operations",
            OperationClass.ANALYZE, BindingType.GRPC,
            scopes=["sip:network:read"],
            parameters={"target_ip": "192.168.1.1"},
        )
        adapter = GrpcAdapter()
        result = adapter.translate(plan)
        assert result.payload["request_message"]["target_ip"] == "192.168.1.1"


class TestA2aAdapterExtended:
    def test_delegation_context_has_trace_ids(self) -> None:
        plan = _make_plan(
            "delegate_agent_task", "agent_orchestration",
            OperationClass.DELEGATE, BindingType.A2A,
            scopes=["sip:agent:delegate"],
            trust_level=TrustLevel.PRIVILEGED,
        )
        adapter = A2aAdapter()
        result = adapter.translate(plan)
        ctx = result.payload["delegation_context"]
        assert "trace_id" in ctx
        assert "intent_id" in ctx
        assert "delegating_plan_id" in ctx

    def test_task_payload_has_capability_id(self) -> None:
        plan = _make_plan(
            "delegate_agent_task", "agent_orchestration",
            OperationClass.DELEGATE, BindingType.A2A,
            scopes=["sip:agent:delegate"],
            trust_level=TrustLevel.PRIVILEGED,
        )
        adapter = A2aAdapter()
        result = adapter.translate(plan)
        assert "capability_id" in result.payload["task_payload"]

    def test_agent_task_type_matches_capability(self) -> None:
        plan = _make_plan(
            "delegate_agent_task", "agent_orchestration",
            OperationClass.DELEGATE, BindingType.A2A,
            scopes=["sip:agent:delegate"],
            trust_level=TrustLevel.PRIVILEGED,
        )
        adapter = A2aAdapter()
        result = adapter.translate(plan)
        assert result.payload["agent_task_type"] == plan.selected_capability.capability_id
