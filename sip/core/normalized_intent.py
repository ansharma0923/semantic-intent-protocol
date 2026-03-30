"""Canonical internal normalized intent model for SIP.

The ``NormalizedIntent`` is an internal representation that is produced from
an ``IntentEnvelope`` (or from a raw request dict) at the beginning of the
SIP processing pipeline.  It is never exposed on the wire; the
``IntentEnvelope`` remains the external protocol object.

Responsibilities:
* Carry a fully normalized and validated internal view of the actor's intent.
* Provide a stable, version-independent shape for policy and planning.
* Capture the raw source request for audit purposes.

Architecture note
-----------------
All pipeline stages downstream of ingestion operate on ``NormalizedIntent``
so they are decoupled from changes to the wire-level ``IntentEnvelope``
schema.  The ``from_envelope`` adapter handles the conversion and applies
fail-closed validation so callers never need to handle a partially populated
``NormalizedIntent``.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, model_validator

from sip.envelope.models import (
    DataSensitivity,
    IntentEnvelope,
    TrustLevel,
)


# ---------------------------------------------------------------------------
# Version tag for forward compatibility
# ---------------------------------------------------------------------------

NORMALIZED_INTENT_SCHEMA_VERSION = "0.2"


# ---------------------------------------------------------------------------
# Internal sub-models
# ---------------------------------------------------------------------------


class NormalizedActor(BaseModel):
    """Normalized representation of the originating actor."""

    actor_id: str
    actor_type: str
    name: str
    trust_level: TrustLevel
    scopes: list[str] = Field(default_factory=list)
    originator: str | None = None
    delegation_chain: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


class NormalizedConstraints(BaseModel):
    """Flattened execution constraints extracted from the envelope."""

    time_budget_ms: int | None = None
    cost_budget: float | None = None
    data_sensitivity: DataSensitivity = DataSensitivity.INTERNAL
    determinism_required: str = "strict"
    priority: str = "normal"
    allowed_actions: list[str] = Field(default_factory=list)
    forbidden_actions: list[str] = Field(default_factory=list)

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# NormalizedIntent – the canonical internal model
# ---------------------------------------------------------------------------


class NormalizedIntent(BaseModel):
    """Canonical internal normalized intent model.

    Fields
    ------
    intent_id
        Unique identifier for this intent (copied from IntentEnvelope.intent_id).
    correlation_id
        Correlation / trace identifier (copied from IntentEnvelope.trace_id).
    schema_version
        Version of this schema; allows downstream systems to detect format
        changes without inspecting field contents.
    actor
        Normalized actor descriptor.
    tenant
        Optional tenant or organisation identifier.  Extracted from
        ``IntentEnvelope.context.additional['tenant']`` when present.
    goal
        A human-readable statement of what the actor wants to achieve.
        Copied from ``desired_outcome.summary``.
    constraints
        Flattened execution constraints.
    required_capabilities
        List of required capability names extracted from capability_requirements.
    risk_level
        Declared risk level (may be None if not specified in the envelope).
    compliance_requirements
        List of compliance requirement strings extracted from
        ``context.additional['compliance']`` when present.
    data_sensitivity
        Maximum data sensitivity permitted; mirrors constraints.data_sensitivity.
    jurisdiction
        Jurisdiction string extracted from ``context.additional['jurisdiction']``
        when present.
    preferred_execution_mode
        Preferred execution mode extracted from the first protocol binding or
        ``negotiation`` hints.
    trust_requirements
        Minimum trust level derived from capability requirements or the
        envelope's trust block.
    raw_request
        The original ``IntentEnvelope`` serialised to a dict for audit purposes.
    metadata
        Arbitrary additional metadata; includes the envelope context.
    created_at
        UTC timestamp when this NormalizedIntent was created.
    """

    intent_id: str = Field(description="Unique intent identifier.")
    correlation_id: str = Field(description="Correlation / trace identifier.")
    schema_version: str = Field(
        default=NORMALIZED_INTENT_SCHEMA_VERSION,
        description="Version of the NormalizedIntent schema.",
    )
    actor: NormalizedActor = Field(description="Normalized actor descriptor.")
    tenant: str | None = Field(
        default=None,
        description="Optional tenant or organisation identifier.",
    )
    goal: str = Field(description="Statement of the actor's desired goal.", min_length=1)
    constraints: NormalizedConstraints = Field(
        description="Flattened execution constraints.",
    )
    required_capabilities: list[str] = Field(
        default_factory=list,
        description="Required capability names.",
    )
    risk_level: str | None = Field(
        default=None,
        description="Declared risk level, if any.",
    )
    compliance_requirements: list[str] = Field(
        default_factory=list,
        description="Compliance requirement strings.",
    )
    data_sensitivity: DataSensitivity = Field(
        description="Maximum data sensitivity permitted.",
    )
    jurisdiction: str | None = Field(
        default=None,
        description="Jurisdiction string, if provided.",
    )
    preferred_execution_mode: str | None = Field(
        default=None,
        description="Preferred execution mode (binding type).",
    )
    trust_requirements: TrustLevel = Field(
        description="Minimum trust level required.",
    )
    raw_request: dict[str, Any] = Field(
        description="The original request serialised for audit purposes.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional metadata.",
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        description="UTC timestamp when this NormalizedIntent was created.",
    )

    @model_validator(mode="after")
    def _validate_critical_fields(self) -> "NormalizedIntent":
        """Fail closed if critical fields are missing."""
        if not self.intent_id:
            raise ValueError("NormalizedIntent.intent_id must not be empty.")
        if not self.correlation_id:
            raise ValueError("NormalizedIntent.correlation_id must not be empty.")
        if not self.goal:
            raise ValueError("NormalizedIntent.goal must not be empty.")
        if not self.actor.actor_id:
            raise ValueError("NormalizedIntent.actor.actor_id must not be empty.")
        return self

    model_config = {"frozen": True}


# ---------------------------------------------------------------------------
# Adapter: IntentEnvelope → NormalizedIntent
# ---------------------------------------------------------------------------


def from_envelope(envelope: IntentEnvelope) -> NormalizedIntent:
    """Convert an ``IntentEnvelope`` into a ``NormalizedIntent``.

    This is the canonical adapter from the external protocol object to the
    internal normalized model.  It fails closed: any critical field that is
    missing (intent_id, correlation_id, actor identity, goal) will raise a
    ``ValueError`` so the pipeline never processes a partially valid intent.

    Args:
        envelope: A fully parsed ``IntentEnvelope``.

    Returns:
        A ``NormalizedIntent`` ready for policy evaluation and planning.

    Raises:
        ValueError: If any critical field is missing or invalid.
    """
    prov = envelope.provenance

    # Build normalized actor (includes originator / delegation chain from provenance)
    actor = NormalizedActor(
        actor_id=envelope.actor.actor_id,
        actor_type=envelope.actor.actor_type.value,
        name=envelope.actor.name,
        trust_level=envelope.actor.trust_level,
        scopes=list(envelope.actor.scopes),
        originator=prov.originator if prov else None,
        delegation_chain=list(prov.delegation_chain) if prov else [],
    )

    # Flatten constraints
    constraints = NormalizedConstraints(
        time_budget_ms=envelope.constraints.time_budget_ms,
        cost_budget=envelope.constraints.cost_budget,
        data_sensitivity=envelope.constraints.data_sensitivity,
        determinism_required=envelope.constraints.determinism_required.value,
        priority=envelope.constraints.priority.value,
        allowed_actions=list(envelope.constraints.allowed_actions),
        forbidden_actions=list(envelope.constraints.forbidden_actions),
    )

    # Extract required capability names
    required_capabilities = [r.capability_name for r in envelope.capability_requirements]

    # Extract preferred execution mode from first protocol binding
    preferred_execution_mode: str | None = None
    if envelope.protocol_bindings:
        preferred_execution_mode = envelope.protocol_bindings[0].binding_type.value

    # Determine minimum trust requirements across capability requirements
    trust_requirements: TrustLevel = envelope.trust.declared_trust_level
    for req in envelope.capability_requirements:
        if req.minimum_trust_tier.value > trust_requirements.value:
            trust_requirements = req.minimum_trust_tier

    # Extract optional fields from context.additional
    additional = envelope.context.additional
    tenant = additional.get("tenant")
    jurisdiction = additional.get("jurisdiction")
    compliance_requirements: list[str] = []
    raw_compliance = additional.get("compliance")
    if isinstance(raw_compliance, list):
        compliance_requirements = [str(c) for c in raw_compliance]
    elif isinstance(raw_compliance, str):
        compliance_requirements = [raw_compliance]

    # Build metadata from context (excluding already-extracted keys)
    metadata: dict[str, Any] = {
        "session_id": envelope.context.session_id,
        "user_locale": envelope.context.user_locale,
        "environment": envelope.context.environment,
        "intent_name": envelope.intent.intent_name,
        "intent_domain": envelope.intent.intent_domain,
        "operation_class": envelope.intent.operation_class.value,
        "natural_language_hint": envelope.intent.natural_language_hint,
        "parameters": dict(envelope.intent.parameters),
    }
    metadata.update(
        {k: v for k, v in additional.items() if k not in ("tenant", "jurisdiction", "compliance")}
    )

    return NormalizedIntent(
        intent_id=envelope.intent_id,
        correlation_id=envelope.trace_id,
        actor=actor,
        tenant=str(tenant) if tenant is not None else None,
        goal=envelope.desired_outcome.summary,
        constraints=constraints,
        required_capabilities=required_capabilities,
        risk_level=None,  # risk_level is a capability property, not declared in envelope
        compliance_requirements=compliance_requirements,
        data_sensitivity=envelope.constraints.data_sensitivity,
        jurisdiction=str(jurisdiction) if jurisdiction is not None else None,
        preferred_execution_mode=preferred_execution_mode,
        trust_requirements=trust_requirements,
        raw_request=envelope.model_dump(mode="json"),
        metadata=metadata,
    )
