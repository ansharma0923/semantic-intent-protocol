"""SIP Python SDK – public entry point.

The SIP Python SDK provides a clean, stable public interface for working
with the Semantic Intent Protocol in Python applications.

Quick start::

    from sip.sdk import (
        IntentEnvelope,
        CapabilityDescriptor,
        NegotiationResult,
        ExecutionPlan,
        AuditRecord,
        BrokerClient,
        CapabilityDiscoveryClient,
        validate_envelope,
    )

Building envelopes::

    from sip.sdk import build_actor, build_intent_envelope

    actor = build_actor(
        actor_id="my-service",
        name="My Service",
        scopes=["sip:knowledge:read"],
    )
    envelope = build_intent_envelope(
        actor=actor,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Retrieve the architecture document.",
    )

Serialization::

    from sip.sdk import to_dict, to_json, parse_intent_envelope

    json_str = to_json(envelope)
    restored  = parse_intent_envelope(json_str)

HTTP clients::

    from sip.sdk import BrokerClient, CapabilityDiscoveryClient

    broker    = BrokerClient("http://localhost:8000")
    discovery = CapabilityDiscoveryClient("http://localhost:8000")
    health    = broker.health()
    caps      = discovery.list_capabilities()

Errors::

    from sip.sdk import SIPError, SIPValidationError, SIPHTTPError, SIPClientError

See ``sip.sdk.models``, ``sip.sdk.builders``, ``sip.sdk.serialization``,
``sip.sdk.clients``, and ``sip.sdk.helpers`` for the full API surface.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------
from sip.sdk.builders import (
    build_actor,
    build_intent_envelope,
    build_protocol_binding,
    build_provenance,
    build_target,
)

# ---------------------------------------------------------------------------
# HTTP clients
# ---------------------------------------------------------------------------
from sip.sdk.clients import (
    BrokerClient,
    CapabilityDiscoveryClient,
)

# ---------------------------------------------------------------------------
# Errors
# ---------------------------------------------------------------------------
from sip.sdk.errors import (
    SIPClientError,
    SIPError,
    SIPHTTPError,
    SIPValidationError,
)

# ---------------------------------------------------------------------------
# Identity / provenance helpers
# ---------------------------------------------------------------------------
from sip.sdk.helpers import (
    apply_identity_headers_to_envelope,
    compute_effective_scope_set,
    merge_identity_context,
    summarize_provenance,
)

# ---------------------------------------------------------------------------
# Models and enums
# ---------------------------------------------------------------------------
from sip.sdk.models import (
    # Observability models
    ActionTaken,
    # Envelope models
    ActorDescriptor,
    # Envelope enums
    ActorType,
    AuditRecord,
    BindingType,
    # Registry / capability models
    CapabilityConstraints,
    CapabilityDescriptor,
    CapabilityExample,
    CapabilityRequirement,
    Constraints,
    ContextBlock,
    DataSensitivity,
    DesiredOutcome,
    DeterminismLevel,
    # Discovery models
    DiscoveryCandidate,
    DiscoveryRequest,
    DiscoveryResponse,
    ExecutionMetadata,
    # Negotiation models
    ExecutionPlan,
    ExecutionPlanner,
    ExecutionStep,
    # Federation models
    FederatedPeer,
    FederationConfig,
    IntegrityBlock,
    IntentEnvelope,
    IntentPayload,
    MessageType,
    NegotiationHints,
    NegotiationResult,
    OperationClass,
    OutcomeSummary,
    PeerTrustLevel,
    PolicyCheckRecord,
    PolicyDecisionSummary,
    Priority,
    ProtocolBinding,
    ProvenanceBlock,
    ProviderMetadata,
    RankedCandidate,
    RemoteCapabilityResult,
    RiskLevel,
    SchemaReference,
    TargetDescriptor,
    TargetType,
    TraceMetadata,
    TrustBlock,
    TrustLevel,
    # Validation
    ValidationResult,
    validate_envelope,
)

# ---------------------------------------------------------------------------
# Serialization helpers
# ---------------------------------------------------------------------------
from sip.sdk.serialization import (
    parse_audit_record,
    parse_capability_descriptor,
    parse_discovery_request,
    parse_discovery_response,
    parse_execution_plan,
    parse_intent_envelope,
    parse_negotiation_result,
    to_dict,
    to_json,
)

__all__ = [
    # Errors
    "SIPError",
    "SIPValidationError",
    "SIPClientError",
    "SIPHTTPError",
    # Envelope enums
    "ActorType",
    "BindingType",
    "DataSensitivity",
    "DeterminismLevel",
    "MessageType",
    "OperationClass",
    "Priority",
    "TargetType",
    "TrustLevel",
    # Envelope models
    "ActorDescriptor",
    "CapabilityRequirement",
    "Constraints",
    "ContextBlock",
    "DesiredOutcome",
    "IntegrityBlock",
    "IntentEnvelope",
    "IntentPayload",
    "NegotiationHints",
    "ProtocolBinding",
    "ProvenanceBlock",
    "TargetDescriptor",
    "TrustBlock",
    # Registry / capability models
    "CapabilityConstraints",
    "CapabilityDescriptor",
    "CapabilityExample",
    "ExecutionMetadata",
    "ProviderMetadata",
    "RiskLevel",
    "SchemaReference",
    # Negotiation models
    "ExecutionPlan",
    "ExecutionPlanner",
    "ExecutionStep",
    "NegotiationResult",
    "PolicyCheckRecord",
    "PolicyDecisionSummary",
    "RankedCandidate",
    "TraceMetadata",
    # Observability models
    "ActionTaken",
    "AuditRecord",
    "OutcomeSummary",
    # Discovery models
    "DiscoveryCandidate",
    "DiscoveryRequest",
    "DiscoveryResponse",
    # Federation models
    "FederatedPeer",
    "FederationConfig",
    "PeerTrustLevel",
    "RemoteCapabilityResult",
    # Validation
    "ValidationResult",
    "validate_envelope",
    # Serialization
    "to_dict",
    "to_json",
    "parse_audit_record",
    "parse_capability_descriptor",
    "parse_discovery_request",
    "parse_discovery_response",
    "parse_execution_plan",
    "parse_intent_envelope",
    "parse_negotiation_result",
    # Builders
    "build_actor",
    "build_intent_envelope",
    "build_protocol_binding",
    "build_provenance",
    "build_target",
    # HTTP clients
    "BrokerClient",
    "CapabilityDiscoveryClient",
    # Helpers
    "apply_identity_headers_to_envelope",
    "compute_effective_scope_set",
    "merge_identity_context",
    "summarize_provenance",
]
