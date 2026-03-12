"""Public SDK model re-exports for the SIP Python SDK.

This module re-exports all protocol models that external SDK consumers need.
Import from here instead of the internal implementation modules.

Example::

    from sip.sdk.models import IntentEnvelope, CapabilityDescriptor

All classes listed in ``__all__`` are considered part of the public SDK
surface and will remain stable across minor versions.
"""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Discovery models
# ---------------------------------------------------------------------------
from sip.broker.discovery import (
    DiscoveryCandidate,
    DiscoveryRequest,
    DiscoveryResponse,
)

# ---------------------------------------------------------------------------
# Federation models
# ---------------------------------------------------------------------------
from sip.broker.federation import (
    FederatedPeer,
    FederationConfig,
    PeerTrustLevel,
    RemoteCapabilityResult,
)

# ---------------------------------------------------------------------------
# Envelope models and enumerations
# ---------------------------------------------------------------------------
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    CapabilityRequirement,
    Constraints,
    ContextBlock,
    DataSensitivity,
    DesiredOutcome,
    DeterminismLevel,
    IntegrityBlock,
    IntentEnvelope,
    IntentPayload,
    MessageType,
    NegotiationHints,
    OperationClass,
    Priority,
    ProtocolBinding,
    ProvenanceBlock,
    TargetDescriptor,
    TargetType,
    TrustBlock,
    TrustLevel,
)

# ---------------------------------------------------------------------------
# Envelope validation
# ---------------------------------------------------------------------------
from sip.envelope.validator import ValidationResult, validate_envelope
from sip.negotiation.planner import (
    ExecutionPlan,
    ExecutionPlanner,
    ExecutionStep,
    PolicyCheckRecord,
    TraceMetadata,
)

# ---------------------------------------------------------------------------
# Negotiation models
# ---------------------------------------------------------------------------
from sip.negotiation.results import (
    NegotiationResult,
    PolicyDecisionSummary,
    RankedCandidate,
)

# ---------------------------------------------------------------------------
# Observability models
# ---------------------------------------------------------------------------
from sip.observability.audit import (
    ActionTaken,
    AuditRecord,
    OutcomeSummary,
)

# ---------------------------------------------------------------------------
# Registry / capability models
# ---------------------------------------------------------------------------
from sip.registry.models import (
    CapabilityConstraints,
    CapabilityDescriptor,
    CapabilityExample,
    ExecutionMetadata,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)

__all__ = [
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
]
