# SIP Capability Model

## What is a Capability?

A SIP capability is a named, typed, policy-controlled operation that can be
discovered, negotiated, and invoked through the SIP protocol.

Capabilities are described using `CapabilityDescriptor` objects registered in
the capability registry. They are the bridge between semantic intent and
deterministic execution.

## Capability Descriptor Fields

### Core Identity

- `capability_id` – Unique machine-readable identifier (e.g. `retrieve_document`)
- `name` – Human-readable name
- `description` – What the capability does

### Provider

- `provider_id` – Unique provider identifier
- `provider_name` – Human-readable provider name
- `version` – Provider's version of this capability

### Semantic Classification

- `intent_domains` – List of functional domains (e.g. `["knowledge_management", "document_retrieval"]`)
- `operation_class` – `read`, `write`, `execute`, `analyze`, `retrieve`, or `delegate`
- `tags` – Searchable labels

### Schema

- `input_schema` – Describes expected input (properties and required fields)
- `output_schema` – Describes expected output (properties and format)

### Trust and Security

- `minimum_trust_tier` – Minimum actor trust level required
- `required_scopes` – Permission scopes the actor must hold
- `risk_level` – `low`, `medium`, `high`, or `critical`

### Execution

- `supported_bindings` – Which protocols can execute this capability
- `execution.average_latency_ms` – Expected latency
- `execution.idempotent` – Whether repeated calls are safe
- `execution.supports_dry_run` – Whether a preview/dry-run mode exists

### Constraints

- `constraints.rate_limit_per_minute` – Max invocations per minute
- `constraints.requires_human_approval` – Always requires approval

## Seeded Capabilities

The v0.1 reference implementation includes nine seeded capabilities:

| Capability ID | Domain | Operation | Risk | Bindings |
|---|---|---|---|---|
| `retrieve_document` | knowledge_management | retrieve | low | rag, rest |
| `search_knowledge_base` | knowledge_management | retrieve | low | rag, rest |
| `summarize_document` | summarization | analyze | low | rest, mcp |
| `reserve_table` | booking | write | medium | rest, mcp |
| `diagnose_network_issue` | network_operations | analyze | medium | rest, grpc, mcp |
| `query_customer_data` | customer_management | read | medium | rest, grpc |
| `collect_device_telemetry` | network_operations | read | low | grpc, rest, a2a |
| `summarize_for_customer` | summarization | analyze | low | rest, mcp, a2a |
| `delegate_agent_task` | agent_orchestration | delegate | medium | a2a, rest |

## Capability Registration

```python
from sip.registry.service import CapabilityRegistryService
from sip.registry.models import CapabilityDescriptor, ProviderMetadata, SchemaReference
from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.models import RiskLevel

registry = CapabilityRegistryService()

my_capability = CapabilityDescriptor(
    capability_id="my_capability",
    name="My Capability",
    description="Does something useful.",
    provider=ProviderMetadata(provider_id="my_service", provider_name="My Service"),
    intent_domains=["my_domain"],
    input_schema=SchemaReference(
        description="Input",
        properties={"query": "string"},
        required_fields=["query"],
    ),
    output_schema=SchemaReference(description="Output"),
    operation_class=OperationClass.READ,
    risk_level=RiskLevel.LOW,
    required_scopes=["sip:my_domain:read"],
    minimum_trust_tier=TrustLevel.INTERNAL,
    supported_bindings=[BindingType.REST],
)

registry.register(my_capability)
```

## Capability Matching

The registry's `find_matches()` method uses deterministic scoring to rank
capabilities against an intent. See [protocol-spec-v0.1.md](protocol-spec-v0.1.md)
section 6 for the full scoring algorithm.

Key design principle: **Matching never calls an LLM**. It is purely based on
string comparison, domain taxonomy, operation class, binding preference, and
trust compatibility.
