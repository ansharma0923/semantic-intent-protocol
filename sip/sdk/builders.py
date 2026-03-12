"""Builder helpers for constructing common SIP protocol objects.

These helpers reduce boilerplate when creating protocol objects from scratch.
They accept commonly-needed arguments and set safe, deterministic defaults
for all optional fields.

Example::

    from sip.sdk.builders import build_intent_envelope, build_actor

    actor = build_actor(
        actor_id="my-service",
        name="My Service",
        actor_type="service",
        trust_level="internal",
        scopes=["sip:knowledge:read"],
    )
    envelope = build_intent_envelope(
        actor=actor,
        intent_name="retrieve_document",
        intent_domain="knowledge_management",
        operation_class="retrieve",
        outcome_summary="Get the architecture document.",
    )

These builders always produce valid objects and raise ``SIPValidationError``
if required fields are missing or invalid.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import ValidationError

from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    Constraints,
    ContextBlock,
    DataSensitivity,
    DesiredOutcome,
    DeterminismLevel,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    ProvenanceBlock,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.sdk.errors import SIPValidationError


def _wrap_validation(func_name: str, exc: ValidationError) -> SIPValidationError:
    errors = [str(e) for e in exc.errors()]
    return SIPValidationError(f"Failed to build {func_name}", errors=errors)


def build_actor(
    actor_id: str,
    name: str,
    actor_type: ActorType | str = ActorType.SERVICE,
    trust_level: TrustLevel | str = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
) -> ActorDescriptor:
    """Build an ``ActorDescriptor``.

    Args:
        actor_id: Unique identifier for the actor.
        name: Human-readable actor name.
        actor_type: ``ActorType`` or its string value (default: ``"service"``).
        trust_level: ``TrustLevel`` or its string value (default: ``"internal"``).
        scopes: Permission scopes granted to the actor.

    Returns:
        A validated ``ActorDescriptor``.

    Raises:
        SIPValidationError: If required fields are missing or invalid.
    """
    try:
        return ActorDescriptor(
            actor_id=actor_id,
            name=name,
            actor_type=ActorType(actor_type) if isinstance(actor_type, str) else actor_type,
            trust_level=TrustLevel(trust_level) if isinstance(trust_level, str) else trust_level,
            scopes=scopes or [],
        )
    except (ValidationError, ValueError) as exc:
        raise SIPValidationError(f"Failed to build ActorDescriptor: {exc}") from exc


def build_target(
    target_type: TargetType | str = TargetType.CAPABILITY,
    target_id: str | None = None,
    namespace: str | None = None,
) -> TargetDescriptor:
    """Build a ``TargetDescriptor``.

    Args:
        target_type: ``TargetType`` or its string value (default: ``"capability"``).
        target_id: Optional specific target identifier.
        namespace: Optional namespace or domain qualifier.

    Returns:
        A validated ``TargetDescriptor``.

    Raises:
        SIPValidationError: If the target type value is invalid.
    """
    try:
        return TargetDescriptor(
            target_type=TargetType(target_type) if isinstance(target_type, str) else target_type,
            target_id=target_id,
            namespace=namespace,
        )
    except (ValidationError, ValueError) as exc:
        raise SIPValidationError(f"Failed to build TargetDescriptor: {exc}") from exc


def build_provenance(
    originator: str | None = None,
    submitted_by: str | None = None,
    delegation_chain: list[str] | None = None,
    on_behalf_of: str | None = None,
    delegation_purpose: str | None = None,
    delegation_expiry: datetime | None = None,
    authority_scope: list[str] | None = None,
) -> ProvenanceBlock:
    """Build a ``ProvenanceBlock``.

    Args:
        originator: Identifier of the entity that originally created the intent.
        submitted_by: Identifier of the actor submitting the envelope.
        delegation_chain: Ordered list of actor IDs in the delegation chain.
        on_behalf_of: The principal on whose behalf the intent is submitted.
        delegation_purpose: Human-readable reason for delegation.
        delegation_expiry: UTC datetime after which the delegation expires.
        authority_scope: Scopes granted by the delegating actor.

    Returns:
        A validated ``ProvenanceBlock``.

    Raises:
        SIPValidationError: If the data is invalid.
    """
    try:
        return ProvenanceBlock(
            originator=originator,
            submitted_by=submitted_by,
            delegation_chain=delegation_chain or [],
            on_behalf_of=on_behalf_of,
            delegation_purpose=delegation_purpose,
            delegation_expiry=delegation_expiry,
            authority_scope=authority_scope,
        )
    except (ValidationError, ValueError) as exc:
        raise SIPValidationError(f"Failed to build ProvenanceBlock: {exc}") from exc


def build_protocol_binding(
    binding_type: BindingType | str,
    endpoint: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> ProtocolBinding:
    """Build a ``ProtocolBinding``.

    Args:
        binding_type: ``BindingType`` or its string value (e.g. ``"rest"``).
        endpoint: Optional target endpoint URI or address.
        metadata: Optional binding-specific metadata.

    Returns:
        A validated ``ProtocolBinding``.

    Raises:
        SIPValidationError: If the binding type value is invalid.
    """
    try:
        return ProtocolBinding(
            binding_type=BindingType(binding_type) if isinstance(binding_type, str) else binding_type,
            endpoint=endpoint,
            metadata=metadata or {},
        )
    except (ValidationError, ValueError) as exc:
        raise SIPValidationError(f"Failed to build ProtocolBinding: {exc}") from exc


def build_intent_envelope(
    actor: ActorDescriptor,
    intent_name: str,
    intent_domain: str,
    operation_class: OperationClass | str,
    outcome_summary: str,
    *,
    target_type: TargetType | str = TargetType.CAPABILITY,
    target_id: str | None = None,
    intent_parameters: dict[str, Any] | None = None,
    natural_language_hint: str | None = None,
    constraints: Constraints | None = None,
    context: ContextBlock | None = None,
    protocol_bindings: list[ProtocolBinding] | None = None,
    provenance: ProvenanceBlock | None = None,
    output_format: str | None = None,
    success_criteria: list[str] | None = None,
    data_sensitivity: DataSensitivity | str = DataSensitivity.INTERNAL,
    determinism_required: DeterminismLevel | str = DeterminismLevel.STRICT,
    extensions: dict[str, Any] | None = None,
) -> IntentEnvelope:
    """Build an ``IntentEnvelope`` with safe defaults.

    This is the primary convenience constructor for SDK consumers. It
    requires only the most essential fields and applies safe defaults for
    everything else.

    Args:
        actor: The actor originating the intent. Use :func:`build_actor`.
        intent_name: Machine-readable intent name (e.g. ``"retrieve_document"``).
        intent_domain: Functional domain (e.g. ``"knowledge_management"``).
        operation_class: ``OperationClass`` or string (e.g. ``"retrieve"``).
        outcome_summary: Brief description of the expected outcome.
        target_type: Target type (default: ``"capability"``).
        target_id: Optional specific target identifier.
        intent_parameters: Optional structured parameters for the intent.
        natural_language_hint: Optional natural-language annotation (audit only).
        constraints: Optional execution constraints. A default is built if omitted.
        context: Optional contextual information block.
        protocol_bindings: Optional list of protocol binding preferences.
        provenance: Optional provenance and delegation metadata.
        output_format: Expected output format (e.g. ``"json"``).
        success_criteria: List of conditions that define a successful outcome.
        data_sensitivity: Data sensitivity level (default: ``"internal"``).
        determinism_required: Required determinism level (default: ``"strict"``).
        extensions: Optional protocol extension fields.

    Returns:
        A validated, frozen ``IntentEnvelope``.

    Raises:
        SIPValidationError: If required fields are missing or invalid.
    """
    try:
        op_class = (
            OperationClass(operation_class)
            if isinstance(operation_class, str)
            else operation_class
        )
        target = build_target(target_type=target_type, target_id=target_id)
        intent = IntentPayload(
            intent_name=intent_name,
            intent_domain=intent_domain,
            operation_class=op_class,
            natural_language_hint=natural_language_hint,
            parameters=intent_parameters or {},
        )
        desired_outcome = DesiredOutcome(
            summary=outcome_summary,
            output_format=output_format,
            success_criteria=success_criteria or [],
        )
        if constraints is None:
            constraints = Constraints(
                data_sensitivity=(
                    DataSensitivity(data_sensitivity)
                    if isinstance(data_sensitivity, str)
                    else data_sensitivity
                ),
                determinism_required=(
                    DeterminismLevel(determinism_required)
                    if isinstance(determinism_required, str)
                    else determinism_required
                ),
            )
        return IntentEnvelope(
            actor=actor,
            target=target,
            intent=intent,
            desired_outcome=desired_outcome,
            constraints=constraints,
            context=context or ContextBlock(),
            protocol_bindings=protocol_bindings or [],
            provenance=provenance,
            extensions=extensions or {},
        )
    except (ValidationError, ValueError) as exc:
        raise SIPValidationError(f"Failed to build IntentEnvelope: {exc}") from exc


__all__ = [
    "build_actor",
    "build_intent_envelope",
    "build_protocol_binding",
    "build_provenance",
    "build_target",
]
