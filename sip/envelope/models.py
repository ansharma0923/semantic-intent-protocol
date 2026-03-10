"""Intent envelope models for the Semantic Intent Protocol.

The IntentEnvelope is the core protocol object that carries a semantic intent
from an actor to a target. All fields are strongly typed via Pydantic.
"""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class ActorType(StrEnum):
    """Types of actors that can originate an intent."""

    HUMAN = "human"
    AI_AGENT = "ai_agent"
    SERVICE = "service"
    SYSTEM = "system"


class TargetType(StrEnum):
    """Types of targets that can receive an intent."""

    CAPABILITY = "capability"
    AGENT = "agent"
    SERVICE = "service"
    REGISTRY = "registry"
    BROADCAST = "broadcast"


class OperationClass(StrEnum):
    """High-level classification of the operation being requested."""

    READ = "read"
    WRITE = "write"
    EXECUTE = "execute"
    ANALYZE = "analyze"
    RETRIEVE = "retrieve"
    DELEGATE = "delegate"


class Priority(StrEnum):
    """Execution priority hint."""

    LOW = "low"
    NORMAL = "normal"
    HIGH = "high"
    CRITICAL = "critical"


class DeterminismLevel(StrEnum):
    """Required determinism level for execution."""

    STRICT = "strict"       # Fully deterministic; same input → same output
    BOUNDED = "bounded"     # Non-deterministic within defined bounds
    ADVISORY = "advisory"   # Best-effort; result may vary


class TrustLevel(StrEnum):
    """Trust tier of the originating actor."""

    PUBLIC = "public"
    INTERNAL = "internal"
    PRIVILEGED = "privileged"
    ADMIN = "admin"


class DataSensitivity(StrEnum):
    """Data sensitivity classification."""

    PUBLIC = "public"
    INTERNAL = "internal"
    CONFIDENTIAL = "confidential"
    RESTRICTED = "restricted"


class BindingType(StrEnum):
    """Supported execution protocol bindings."""

    REST = "rest"
    GRPC = "grpc"
    MCP = "mcp"
    A2A = "a2a"
    RAG = "rag"


class MessageType(StrEnum):
    """SIP message type classification."""

    INTENT_REQUEST = "intent_request"
    INTENT_RESPONSE = "intent_response"
    CAPABILITY_QUERY = "capability_query"
    CAPABILITY_RESPONSE = "capability_response"
    NEGOTIATION_RESULT = "negotiation_result"
    EXECUTION_PLAN = "execution_plan"
    AUDIT_RECORD = "audit_record"


# ---------------------------------------------------------------------------
# Nested models
# ---------------------------------------------------------------------------


class ActorDescriptor(BaseModel):
    """Describes the entity originating the intent."""

    actor_id: str = Field(description="Unique identifier for the actor.")
    actor_type: ActorType = Field(description="Type of the actor.")
    name: str = Field(description="Human-readable actor name.")
    trust_level: TrustLevel = Field(
        default=TrustLevel.INTERNAL,
        description="Trust level assigned to this actor.",
    )
    scopes: list[str] = Field(
        default_factory=list,
        description="List of permission scopes granted to this actor.",
    )


class TargetDescriptor(BaseModel):
    """Describes the intended target of an intent."""

    target_type: TargetType = Field(description="Type of the target.")
    target_id: str | None = Field(
        default=None,
        description="Specific target identifier (optional for broadcasts).",
    )
    namespace: str | None = Field(
        default=None,
        description="Optional namespace or domain qualifier.",
    )


class IntentPayload(BaseModel):
    """The semantic intent being expressed."""

    intent_name: str = Field(
        description="Short machine-readable intent name (e.g. 'retrieve_document')."
    )
    intent_domain: str = Field(
        description="Functional domain of the intent (e.g. 'knowledge_management')."
    )
    operation_class: OperationClass = Field(
        description="High-level classification of the operation."
    )
    natural_language_hint: str | None = Field(
        default=None,
        description=(
            "Optional natural-language description for logging/auditing only. "
            "Never executed directly."
        ),
    )
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Structured parameters for the intent.",
    )


class DesiredOutcome(BaseModel):
    """Describes what the actor wants as a result."""

    summary: str = Field(description="Brief description of the expected outcome.")
    output_format: str | None = Field(
        default=None,
        description="Expected output format (e.g. 'json', 'markdown', 'pdf').",
    )
    success_criteria: list[str] = Field(
        default_factory=list,
        description="Conditions that define a successful outcome.",
    )


class Constraints(BaseModel):
    """Execution constraints on the intent."""

    time_budget_ms: int | None = Field(
        default=None,
        description="Maximum allowed execution time in milliseconds.",
    )
    cost_budget: float | None = Field(
        default=None,
        description="Maximum allowed cost in abstract cost units.",
    )
    allowed_actions: list[str] = Field(
        default_factory=list,
        description="Explicit list of permitted action types.",
    )
    forbidden_actions: list[str] = Field(
        default_factory=list,
        description="Explicit list of forbidden action types.",
    )
    data_sensitivity: DataSensitivity = Field(
        default=DataSensitivity.INTERNAL,
        description="Maximum data sensitivity level permitted.",
    )
    determinism_required: DeterminismLevel = Field(
        default=DeterminismLevel.STRICT,
        description="Required determinism level for execution.",
    )
    priority: Priority = Field(
        default=Priority.NORMAL,
        description="Execution priority hint.",
    )

    @field_validator("time_budget_ms")
    @classmethod
    def time_budget_must_be_positive(cls, v: int | None) -> int | None:
        if v is not None and v < 0:
            raise ValueError("time_budget_ms must be non-negative.")
        return v

    @field_validator("cost_budget")
    @classmethod
    def cost_budget_must_be_positive(cls, v: float | None) -> float | None:
        if v is not None and v < 0.0:
            raise ValueError("cost_budget must be non-negative.")
        return v


class ContextBlock(BaseModel):
    """Contextual information attached to the intent."""

    session_id: str | None = Field(default=None)
    user_locale: str | None = Field(default=None)
    environment: str = Field(
        default="production",
        description="Deployment environment (e.g. 'production', 'staging').",
    )
    additional: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional context key-value pairs.",
    )


class CapabilityRequirement(BaseModel):
    """Describes a required capability for this intent."""

    capability_name: str = Field(
        description="Name or pattern of the required capability."
    )
    required_scopes: list[str] = Field(default_factory=list)
    preferred_binding: BindingType | None = Field(default=None)
    minimum_trust_tier: TrustLevel = Field(default=TrustLevel.INTERNAL)


class TrustBlock(BaseModel):
    """Trust and credential information for the intent."""

    declared_trust_level: TrustLevel = Field(default=TrustLevel.INTERNAL)
    delegation_chain: list[str] = Field(
        default_factory=list,
        description="Ordered list of actor IDs representing the delegation chain.",
    )
    token_reference: str | None = Field(
        default=None,
        description="Reference to an external auth token (not the token itself).",
    )


class ProtocolBinding(BaseModel):
    """Specifies how this intent should be bound to an execution protocol."""

    binding_type: BindingType = Field(description="Target execution protocol.")
    endpoint: str | None = Field(
        default=None,
        description="Target endpoint URI or address.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Binding-specific metadata.",
    )


class NegotiationHints(BaseModel):
    """Optional hints to guide capability negotiation."""

    candidate_capabilities: list[str] = Field(
        default_factory=list,
        description="Preferred capability IDs to consider first.",
    )
    allow_fallback: bool = Field(
        default=True,
        description="Whether to allow fallback to alternative capabilities.",
    )
    max_candidates: int = Field(
        default=5,
        description="Maximum number of candidates to evaluate.",
    )


class IntegrityBlock(BaseModel):
    """Integrity and provenance metadata for the envelope."""

    schema_version: str = Field(default="0.1")
    signed: bool = Field(
        default=False,
        description="Whether the envelope is cryptographically signed.",
    )
    signature_reference: str | None = Field(
        default=None,
        description="Reference to the signature (not inline for security).",
    )


# ---------------------------------------------------------------------------
# Root envelope
# ---------------------------------------------------------------------------


class IntentEnvelope(BaseModel):
    """The root SIP protocol object – an intent envelope.

    An IntentEnvelope carries a structured semantic intent from an actor to a
    target system. It includes trust, policy constraints, context, negotiation
    hints, and execution binding preferences.

    The envelope is immutable after creation; all mutation creates a new instance.
    """

    sip_version: str = Field(
        default="0.1",
        description="SIP protocol version.",
    )
    message_type: MessageType = Field(
        default=MessageType.INTENT_REQUEST,
        description="SIP message type.",
    )
    intent_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique identifier for this intent.",
    )
    trace_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Distributed trace identifier.",
    )
    span_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Current span identifier within the trace.",
    )
    timestamp: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        description="ISO 8601 timestamp when the envelope was created.",
    )
    actor: ActorDescriptor = Field(description="The originating actor.")
    target: TargetDescriptor = Field(description="The intended target.")
    intent: IntentPayload = Field(description="The semantic intent payload.")
    desired_outcome: DesiredOutcome = Field(
        description="The actor's desired outcome."
    )
    constraints: Constraints = Field(
        default_factory=Constraints,
        description="Execution constraints.",
    )
    context: ContextBlock = Field(
        default_factory=ContextBlock,
        description="Contextual information.",
    )
    capability_requirements: list[CapabilityRequirement] = Field(
        default_factory=list,
        description="Capability requirements for this intent.",
    )
    trust: TrustBlock = Field(
        default_factory=TrustBlock,
        description="Trust and credential block.",
    )
    protocol_bindings: list[ProtocolBinding] = Field(
        default_factory=list,
        description="Acceptable protocol bindings in order of preference.",
    )
    negotiation: NegotiationHints = Field(
        default_factory=NegotiationHints,
        description="Negotiation hints.",
    )
    integrity: IntegrityBlock = Field(
        default_factory=IntegrityBlock,
        description="Integrity and provenance metadata.",
    )

    model_config = {"frozen": True}
