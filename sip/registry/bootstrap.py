"""Registry bootstrap – seeds the in-memory registry with example capabilities.

This module provides a ``seed_registry`` function that populates a
CapabilityRegistryService with realistic example capabilities. It is used
by examples, functional tests, and the default broker configuration.

All capability metadata is static and deterministic — no external calls.
"""

from __future__ import annotations

from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.policy.scopes import (
    SCOPE_AGENT_DELEGATE,
    SCOPE_BOOKING_WRITE,
    SCOPE_CUSTOMER_READ,
    SCOPE_KNOWLEDGE_READ,
    SCOPE_NETWORK_READ,
)
from sip.registry.models import (
    CapabilityConstraints,
    CapabilityDescriptor,
    CapabilityExample,
    ExecutionMetadata,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService

# ---------------------------------------------------------------------------
# Provider definitions
# ---------------------------------------------------------------------------

_PROVIDER_KNOWLEDGE = ProviderMetadata(
    provider_id="knowledge_service",
    provider_name="Enterprise Knowledge Service",
    version="1.2.0",
    documentation_url="https://internal.example.com/docs/knowledge",
)

_PROVIDER_BOOKING = ProviderMetadata(
    provider_id="booking_service",
    provider_name="Restaurant Booking Service",
    version="2.0.1",
    documentation_url="https://internal.example.com/docs/booking",
)

_PROVIDER_NETWORK = ProviderMetadata(
    provider_id="network_ops",
    provider_name="Network Operations Platform",
    version="3.1.0",
    documentation_url="https://internal.example.com/docs/network",
)

_PROVIDER_SUMMARIZER = ProviderMetadata(
    provider_id="ai_summarizer",
    provider_name="AI Summarization Service",
    version="1.0.0",
    documentation_url="https://internal.example.com/docs/summarizer",
)

_PROVIDER_AGENT_ORCHESTRATOR = ProviderMetadata(
    provider_id="agent_orchestrator",
    provider_name="Agent Orchestration Platform",
    version="1.0.0",
    documentation_url="https://internal.example.com/docs/orchestrator",
)

_PROVIDER_CUSTOMER = ProviderMetadata(
    provider_id="customer_service",
    provider_name="Customer Data Service",
    version="1.0.0",
    documentation_url="https://internal.example.com/docs/customer",
)

# ---------------------------------------------------------------------------
# Capability definitions
# ---------------------------------------------------------------------------

_CAPABILITIES: list[CapabilityDescriptor] = [
    # 1. retrieve_document
    CapabilityDescriptor(
        capability_id="retrieve_document",
        name="Retrieve Document",
        description=(
            "Retrieve a specific document or file from the enterprise knowledge store "
            "by document ID, name, or query."
        ),
        provider=_PROVIDER_KNOWLEDGE,
        intent_domains=["knowledge_management", "document_retrieval", "enterprise_search"],
        input_schema=SchemaReference(
            description="Document retrieval request",
            properties={
                "document_id": "string (optional)",
                "query": "string (optional)",
                "collection": "string (optional)",
            },
            required_fields=[],
        ),
        output_schema=SchemaReference(
            description="Retrieved document with metadata",
            properties={
                "document_id": "string",
                "title": "string",
                "content": "string",
                "metadata": "object",
            },
        ),
        operation_class=OperationClass.RETRIEVE,
        risk_level=RiskLevel.LOW,
        required_scopes=[SCOPE_KNOWLEDGE_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.RAG, BindingType.REST],
        execution=ExecutionMetadata(average_latency_ms=200, idempotent=True),
        constraints=CapabilityConstraints(
            rate_limit_per_minute=100,
            allowed_environments=["production", "staging", "development"],
        ),
        examples=[
            CapabilityExample(
                name="Retrieve architecture document",
                description="Retrieve the latest approved architecture document.",
                parameters={"query": "approved architecture document", "collection": "architecture"},
                expected_output_summary="Returns document content and metadata.",
            )
        ],
        tags=["knowledge", "document", "retrieval", "read-only"],
    ),

    # 2. search_knowledge_base
    CapabilityDescriptor(
        capability_id="search_knowledge_base",
        name="Search Knowledge Base",
        description=(
            "Perform a semantic or keyword search across one or more knowledge base "
            "collections. Returns ranked results with excerpts."
        ),
        provider=_PROVIDER_KNOWLEDGE,
        intent_domains=["knowledge_management", "enterprise_search", "information_retrieval"],
        input_schema=SchemaReference(
            description="Search request",
            properties={
                "query": "string",
                "collections": "list[string] (optional)",
                "max_results": "integer (optional, default 10)",
                "filters": "object (optional)",
            },
            required_fields=["query"],
        ),
        output_schema=SchemaReference(
            description="Search results with relevance scores",
            properties={
                "results": "list[SearchResult]",
                "total_count": "integer",
            },
        ),
        operation_class=OperationClass.RETRIEVE,
        risk_level=RiskLevel.LOW,
        required_scopes=[SCOPE_KNOWLEDGE_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.RAG, BindingType.REST],
        execution=ExecutionMetadata(average_latency_ms=400, idempotent=True),
        examples=[
            CapabilityExample(
                name="Search for design decisions",
                description="Search for main design decisions in architecture documents.",
                parameters={"query": "main design decisions", "max_results": 5},
                expected_output_summary="Returns top 5 matching document excerpts.",
            )
        ],
        tags=["knowledge", "search", "retrieval", "read-only"],
    ),

    # 3. summarize_document
    CapabilityDescriptor(
        capability_id="summarize_document",
        name="Summarize Document",
        description=(
            "Generate a concise, structured summary of a document. "
            "Input can be document content or a document ID."
        ),
        provider=_PROVIDER_SUMMARIZER,
        intent_domains=["knowledge_management", "document_processing", "summarization"],
        input_schema=SchemaReference(
            description="Document summarization request",
            properties={
                "document_id": "string (optional)",
                "content": "string (optional)",
                "summary_format": "string (optional: bullets | paragraph)",
                "max_length": "integer (optional)",
            },
            required_fields=[],
        ),
        output_schema=SchemaReference(
            description="Document summary",
            properties={
                "summary": "string",
                "key_points": "list[string]",
                "word_count": "integer",
            },
        ),
        operation_class=OperationClass.ANALYZE,
        risk_level=RiskLevel.LOW,
        required_scopes=[SCOPE_KNOWLEDGE_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.REST, BindingType.MCP],
        execution=ExecutionMetadata(average_latency_ms=1500, idempotent=True),
        tags=["summarization", "document", "knowledge", "read-only"],
    ),

    # 4. reserve_table
    CapabilityDescriptor(
        capability_id="reserve_table",
        name="Reserve Restaurant Table",
        description=(
            "Book a restaurant table. Requires date, time, party size, and "
            "customer name. Returns a reservation confirmation."
        ),
        provider=_PROVIDER_BOOKING,
        intent_domains=["booking", "restaurant", "reservation"],
        input_schema=SchemaReference(
            description="Table reservation request",
            properties={
                "restaurant_name": "string (optional)",
                "location": "string (optional)",
                "date": "string (ISO 8601 date)",
                "time": "string (HH:MM)",
                "party_size": "integer",
                "customer_name": "string",
                "special_requests": "string (optional)",
            },
            required_fields=["date", "time", "party_size", "customer_name"],
        ),
        output_schema=SchemaReference(
            description="Reservation confirmation",
            properties={
                "reservation_id": "string",
                "restaurant_name": "string",
                "confirmation_code": "string",
                "status": "string",
            },
        ),
        operation_class=OperationClass.WRITE,
        risk_level=RiskLevel.MEDIUM,
        required_scopes=[SCOPE_BOOKING_WRITE],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.REST, BindingType.MCP],
        execution=ExecutionMetadata(
            average_latency_ms=800,
            idempotent=False,
            supports_dry_run=True,
        ),
        constraints=CapabilityConstraints(
            requires_human_approval=False,
            rate_limit_per_minute=20,
        ),
        examples=[
            CapabilityExample(
                name="Book table for two",
                description="Book a table for 2 near downtown at 7 PM.",
                parameters={
                    "location": "downtown",
                    "date": "2024-12-15",
                    "time": "19:00",
                    "party_size": 2,
                    "customer_name": "Alex",
                },
                expected_output_summary="Returns reservation confirmation with ID.",
            )
        ],
        tags=["booking", "restaurant", "write", "reservation"],
    ),

    # 5. diagnose_network_issue
    CapabilityDescriptor(
        capability_id="diagnose_network_issue",
        name="Diagnose Network Issue",
        description=(
            "Diagnose network problems on a specified device or site. "
            "Collects diagnostics, analyzes symptoms, and returns a "
            "structured diagnosis report."
        ),
        provider=_PROVIDER_NETWORK,
        intent_domains=["network_operations", "diagnostics", "infrastructure"],
        input_schema=SchemaReference(
            description="Network diagnosis request",
            properties={
                "device_id": "string",
                "site": "string (optional)",
                "symptom": "string (optional)",
                "diagnostic_depth": "string (optional: shallow | deep)",
            },
            required_fields=["device_id"],
        ),
        output_schema=SchemaReference(
            description="Network diagnosis report",
            properties={
                "device_id": "string",
                "diagnosis": "string",
                "severity": "string",
                "recommended_actions": "list[string]",
                "raw_metrics": "object",
            },
        ),
        operation_class=OperationClass.ANALYZE,
        risk_level=RiskLevel.MEDIUM,
        required_scopes=[SCOPE_NETWORK_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.REST, BindingType.GRPC, BindingType.MCP],
        execution=ExecutionMetadata(average_latency_ms=3000, idempotent=True),
        tags=["network", "diagnostics", "read-only", "infrastructure"],
    ),

    # 6. query_customer_data
    CapabilityDescriptor(
        capability_id="query_customer_data",
        name="Query Customer Data",
        description=(
            "Query customer records from the CRM system. Returns structured "
            "customer data including account information and history."
        ),
        provider=_PROVIDER_CUSTOMER,
        intent_domains=["customer_management", "crm", "data_retrieval"],
        input_schema=SchemaReference(
            description="Customer data query",
            properties={
                "customer_id": "string (optional)",
                "email": "string (optional)",
                "filters": "object (optional)",
            },
            required_fields=[],
        ),
        output_schema=SchemaReference(
            description="Customer record",
            properties={
                "customer_id": "string",
                "name": "string",
                "email": "string",
                "account_status": "string",
            },
        ),
        operation_class=OperationClass.READ,
        risk_level=RiskLevel.MEDIUM,
        required_scopes=[SCOPE_CUSTOMER_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.REST, BindingType.GRPC],
        execution=ExecutionMetadata(average_latency_ms=150, idempotent=True),
        tags=["customer", "crm", "read-only", "data"],
    ),

    # 7. collect_device_telemetry
    CapabilityDescriptor(
        capability_id="collect_device_telemetry",
        name="Collect Device Telemetry",
        description=(
            "Collect real-time telemetry data from a network device. "
            "Returns metrics including CPU, memory, interface counters, and error rates."
        ),
        provider=_PROVIDER_NETWORK,
        intent_domains=["network_operations", "telemetry", "monitoring"],
        input_schema=SchemaReference(
            description="Telemetry collection request",
            properties={
                "device_id": "string",
                "metrics": "list[string] (optional)",
                "time_window_seconds": "integer (optional)",
            },
            required_fields=["device_id"],
        ),
        output_schema=SchemaReference(
            description="Device telemetry snapshot",
            properties={
                "device_id": "string",
                "collected_at": "string (ISO 8601)",
                "metrics": "object",
            },
        ),
        operation_class=OperationClass.READ,
        risk_level=RiskLevel.LOW,
        required_scopes=[SCOPE_NETWORK_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.GRPC, BindingType.REST, BindingType.A2A],
        execution=ExecutionMetadata(average_latency_ms=500, idempotent=True),
        tags=["telemetry", "network", "monitoring", "read-only"],
    ),

    # 8. summarize_for_customer
    CapabilityDescriptor(
        capability_id="summarize_for_customer",
        name="Summarize for Customer",
        description=(
            "Generate a customer-friendly, plain-language summary of technical "
            "content (e.g. network diagnosis, incident report). "
            "Avoids jargon and focuses on impact and resolution."
        ),
        provider=_PROVIDER_SUMMARIZER,
        intent_domains=["summarization", "customer_communication", "reporting"],
        input_schema=SchemaReference(
            description="Technical content to summarize",
            properties={
                "content": "string",
                "context": "string (optional)",
                "tone": "string (optional: formal | friendly)",
            },
            required_fields=["content"],
        ),
        output_schema=SchemaReference(
            description="Customer-friendly summary",
            properties={
                "summary": "string",
                "impact": "string",
                "resolution": "string",
            },
        ),
        operation_class=OperationClass.ANALYZE,
        risk_level=RiskLevel.LOW,
        required_scopes=[SCOPE_KNOWLEDGE_READ],
        minimum_trust_tier=TrustLevel.INTERNAL,
        supported_bindings=[BindingType.REST, BindingType.MCP, BindingType.A2A],
        execution=ExecutionMetadata(average_latency_ms=2000, idempotent=True),
        tags=["summarization", "customer", "reporting", "read-only"],
    ),

    # 9. delegate_agent_task
    CapabilityDescriptor(
        capability_id="delegate_agent_task",
        name="Delegate Agent Task",
        description=(
            "Delegate a structured task to another SIP-registered agent. "
            "Used for multi-agent orchestration workflows. "
            "The target agent processes the task and returns a structured result."
        ),
        provider=_PROVIDER_AGENT_ORCHESTRATOR,
        intent_domains=["agent_orchestration", "multi_agent", "delegation"],
        input_schema=SchemaReference(
            description="Agent task delegation request",
            properties={
                "target_agent_id": "string",
                "task_type": "string",
                "task_payload": "object",
                "return_format": "string (optional)",
            },
            required_fields=["target_agent_id", "task_type", "task_payload"],
        ),
        output_schema=SchemaReference(
            description="Agent task result",
            properties={
                "task_id": "string",
                "status": "string",
                "result": "object",
                "agent_trace_id": "string",
            },
        ),
        operation_class=OperationClass.DELEGATE,
        risk_level=RiskLevel.MEDIUM,
        required_scopes=[SCOPE_AGENT_DELEGATE],
        minimum_trust_tier=TrustLevel.PRIVILEGED,
        supported_bindings=[BindingType.A2A, BindingType.REST],
        execution=ExecutionMetadata(
            average_latency_ms=5000,
            idempotent=False,
            max_retries=2,
        ),
        tags=["agent", "delegation", "orchestration", "multi-agent"],
    ),
]


def seed_registry(registry: CapabilityRegistryService) -> None:
    """Seed a registry with the standard SIP example capabilities.

    Args:
        registry: The registry service to populate.
    """
    for cap in _CAPABILITIES:
        registry.register(cap)


def build_seeded_registry() -> CapabilityRegistryService:
    """Create and return a new registry pre-seeded with example capabilities."""
    registry = CapabilityRegistryService()
    seed_registry(registry)
    return registry
