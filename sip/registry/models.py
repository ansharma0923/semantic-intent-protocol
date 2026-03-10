"""Capability descriptor models for the SIP registry.

A CapabilityDescriptor fully describes a capability that can be registered,
discovered, and invoked through the SIP protocol.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field

from sip.envelope.models import BindingType, OperationClass, TrustLevel


# ---------------------------------------------------------------------------
# Enumerations
# ---------------------------------------------------------------------------


class RiskLevel(str, Enum):
    """Risk level associated with invoking this capability."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


# ---------------------------------------------------------------------------
# Sub-models
# ---------------------------------------------------------------------------


class ProviderMetadata(BaseModel):
    """Metadata about the provider of a capability."""

    provider_id: str = Field(description="Unique provider identifier.")
    provider_name: str = Field(description="Human-readable provider name.")
    contact: str | None = Field(
        default=None,
        description="Contact email or URL for the provider.",
    )
    version: str = Field(
        default="1.0.0",
        description="Provider's capability version.",
    )
    documentation_url: str | None = Field(
        default=None,
        description="URL to capability documentation.",
    )


class SchemaReference(BaseModel):
    """Reference or inline shape for input/output schemas."""

    schema_id: str | None = Field(
        default=None,
        description="External schema identifier (e.g. JSON Schema $id).",
    )
    description: str = Field(
        default="",
        description="Human-readable description of the schema.",
    )
    properties: dict[str, str] = Field(
        default_factory=dict,
        description="Simplified property-name → type description map.",
    )
    required_fields: list[str] = Field(
        default_factory=list,
        description="List of required field names.",
    )


class ExecutionMetadata(BaseModel):
    """Execution characteristics of the capability."""

    average_latency_ms: int | None = Field(
        default=None,
        description="Expected average execution latency in milliseconds.",
    )
    idempotent: bool = Field(
        default=True,
        description="Whether the capability is idempotent.",
    )
    supports_dry_run: bool = Field(
        default=False,
        description="Whether a dry-run mode is supported.",
    )
    max_retries: int = Field(
        default=3,
        description="Recommended maximum retry count.",
    )


class CapabilityConstraints(BaseModel):
    """Operational constraints for the capability."""

    rate_limit_per_minute: int | None = Field(
        default=None,
        description="Maximum invocations per minute.",
    )
    requires_human_approval: bool = Field(
        default=False,
        description="Whether human approval is always required.",
    )
    allowed_environments: list[str] = Field(
        default_factory=list,
        description="List of allowed deployment environments.",
    )


class CapabilityExample(BaseModel):
    """An example invocation of the capability."""

    name: str = Field(description="Short example name.")
    description: str = Field(description="What this example demonstrates.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Example input parameters.",
    )
    expected_output_summary: str = Field(
        default="",
        description="Brief description of expected output.",
    )


# ---------------------------------------------------------------------------
# Capability descriptor
# ---------------------------------------------------------------------------


class CapabilityDescriptor(BaseModel):
    """Complete descriptor for a SIP-registered capability.

    A capability descriptor provides all information needed for a registry to
    match, rank, and bind an intent to this capability, and for a translator
    adapter to generate a deterministic execution payload.
    """

    capability_id: str = Field(
        description="Unique capability identifier (e.g. 'retrieve_document')."
    )
    name: str = Field(description="Human-readable capability name.")
    description: str = Field(description="What this capability does.")
    provider: ProviderMetadata = Field(description="Provider metadata.")
    intent_domains: list[str] = Field(
        description="Functional domains this capability serves.",
    )
    input_schema: SchemaReference = Field(
        description="Shape or reference for the input schema.",
    )
    output_schema: SchemaReference = Field(
        description="Shape or reference for the output schema.",
    )
    operation_class: OperationClass = Field(
        description="Operation class this capability implements.",
    )
    risk_level: RiskLevel = Field(
        default=RiskLevel.LOW,
        description="Risk level of invoking this capability.",
    )
    required_scopes: list[str] = Field(
        default_factory=list,
        description="Permission scopes required to invoke this capability.",
    )
    minimum_trust_tier: TrustLevel = Field(
        default=TrustLevel.INTERNAL,
        description="Minimum trust level required.",
    )
    supported_bindings: list[BindingType] = Field(
        description="Execution protocol bindings supported by this capability.",
    )
    execution: ExecutionMetadata = Field(
        default_factory=ExecutionMetadata,
        description="Execution characteristics.",
    )
    constraints: CapabilityConstraints = Field(
        default_factory=CapabilityConstraints,
        description="Operational constraints.",
    )
    examples: list[CapabilityExample] = Field(
        default_factory=list,
        description="Example invocations.",
    )
    tags: list[str] = Field(
        default_factory=list,
        description="Searchable tags.",
    )
