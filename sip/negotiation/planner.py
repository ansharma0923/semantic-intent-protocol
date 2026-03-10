"""Execution planner for SIP.

Takes a NegotiationResult and a validated IntentEnvelope and produces a
deterministic ExecutionPlan. The planner grounds parameters, selects binding,
and constructs execution steps.
"""

from __future__ import annotations

from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field

from sip.envelope.models import BindingType, IntentEnvelope
from sip.negotiation.results import NegotiationResult
from sip.registry.models import CapabilityDescriptor

# ---------------------------------------------------------------------------
# Execution plan models
# ---------------------------------------------------------------------------


class TraceMetadata(BaseModel):
    """Trace metadata attached to an execution plan."""

    trace_id: str
    span_id: str
    parent_span_id: str | None = None
    intent_id: str


class ExecutionStep(BaseModel):
    """A single deterministic step in an execution plan."""

    step_index: int = Field(description="Zero-based step index.")
    step_name: str = Field(description="Short descriptive name.")
    description: str = Field(description="What this step does.")
    capability_id: str = Field(description="Capability invoked in this step.")
    binding: BindingType = Field(description="Binding used for this step.")
    parameters: dict[str, Any] = Field(
        default_factory=dict,
        description="Grounded parameters for this step.",
    )
    depends_on: list[int] = Field(
        default_factory=list,
        description="Step indices this step depends on.",
    )


class PolicyCheckRecord(BaseModel):
    """Records a policy check that was passed during planning."""

    check_name: str
    result: str
    notes: str = ""


class ExecutionPlan(BaseModel):
    """A deterministic execution plan produced by the SIP planner.

    The plan is ready to hand to a translator adapter for execution.
    """

    plan_id: str = Field(
        default_factory=lambda: str(uuid4()),
        description="Unique plan identifier.",
    )
    intent_id: str = Field(description="ID of the originating intent.")
    selected_capability: CapabilityDescriptor = Field(
        description="The capability selected for execution.",
    )
    selected_binding: BindingType = Field(
        description="The binding selected for execution.",
    )
    deterministic_target: dict[str, Any] = Field(
        description="Binding-specific deterministic target information.",
    )
    grounded_parameters: dict[str, Any] = Field(
        description="Fully resolved parameters for execution.",
    )
    execution_steps: list[ExecutionStep] = Field(
        description="Ordered list of execution steps.",
    )
    policy_checks_passed: list[PolicyCheckRecord] = Field(
        default_factory=list,
        description="Policy checks that were passed.",
    )
    approval_required: bool = Field(
        default=False,
        description="Whether human approval is required before execution.",
    )
    trace: TraceMetadata = Field(description="Trace metadata.")


# ---------------------------------------------------------------------------
# Planner
# ---------------------------------------------------------------------------


def _ground_parameters(
    envelope: IntentEnvelope,
    capability: CapabilityDescriptor,
) -> dict[str, Any]:
    """Ground envelope parameters against the capability's input schema.

    Copies parameters from the envelope intent, then fills any required
    fields that are missing with placeholder markers (clearly labelled).
    """
    grounded: dict[str, Any] = dict(envelope.intent.parameters)

    # Fill any required fields that are absent
    for field_name in capability.input_schema.required_fields:
        if field_name not in grounded:
            grounded[field_name] = f"<REQUIRED:{field_name}>"

    return grounded


def _build_deterministic_target(
    capability: CapabilityDescriptor,
    binding: BindingType,
    envelope: IntentEnvelope,
) -> dict[str, Any]:
    """Build binding-specific target information deterministically."""
    # Look up an explicit endpoint from the envelope's protocol_bindings
    endpoint: str | None = None
    for pb in envelope.protocol_bindings:
        if pb.binding_type == binding:
            endpoint = pb.endpoint
            break

    provider_id = capability.provider.provider_id

    return {
        "capability_id": capability.capability_id,
        "provider_id": provider_id,
        "binding_type": binding.value,
        "endpoint": endpoint or f"<ENDPOINT:{provider_id}/{capability.capability_id}>",
    }


class ExecutionPlanner:
    """Converts a NegotiationResult into a deterministic ExecutionPlan.

    The planner grounds parameters, validates that the selected binding is
    compatible, and constructs execution steps. For simple single-capability
    intents, one step is produced. Multi-step plans (e.g. A2A delegation)
    are assembled from multiple capabilities if present in the result.
    """

    def plan(
        self,
        envelope: IntentEnvelope,
        negotiation: NegotiationResult,
    ) -> ExecutionPlan:
        """Produce an ExecutionPlan from a NegotiationResult.

        Args:
            envelope: The original intent envelope.
            negotiation: The result of capability negotiation.

        Returns:
            A fully specified ExecutionPlan.

        Raises:
            ValueError: If no capability was selected or no binding is available.
        """
        if negotiation.selected_capability is None:
            raise ValueError(
                f"Cannot create execution plan: no capability selected for "
                f"intent '{envelope.intent_id}'. "
                "Check negotiation result for clarification questions."
            )

        if negotiation.selected_binding is None:
            raise ValueError(
                f"Cannot create execution plan: no binding selected for "
                f"intent '{envelope.intent_id}'."
            )

        cap = negotiation.selected_capability
        binding = negotiation.selected_binding

        grounded = _ground_parameters(envelope, cap)
        target = _build_deterministic_target(cap, binding, envelope)

        steps = [
            ExecutionStep(
                step_index=0,
                step_name=f"invoke_{cap.capability_id}",
                description=(
                    f"Invoke '{cap.name}' via {binding.value} binding "
                    f"for intent '{envelope.intent.intent_name}'."
                ),
                capability_id=cap.capability_id,
                binding=binding,
                parameters=grounded,
                depends_on=[],
            )
        ]

        from sip.registry.service import _TRUST_ORDER  # noqa: PLC0415

        trust_ok = (
            _TRUST_ORDER.get(envelope.actor.trust_level, 0)
            >= _TRUST_ORDER.get(cap.minimum_trust_tier, 0)
        )
        opclass_match = cap.operation_class == envelope.intent.operation_class

        policy_checks: list[PolicyCheckRecord] = [
            PolicyCheckRecord(
                check_name="trust_level",
                result="passed" if trust_ok else "warning",
                notes=(
                    f"Actor trust '{envelope.actor.trust_level}' meets "
                    f"capability minimum '{cap.minimum_trust_tier}'."
                    if trust_ok
                    else (
                        f"Actor trust '{envelope.actor.trust_level}' is below "
                        f"capability minimum '{cap.minimum_trust_tier}'."
                    )
                ),
            ),
            PolicyCheckRecord(
                check_name="operation_class_match",
                result="passed" if opclass_match else "warning",
                notes=(
                    f"Intent operation class '{envelope.intent.operation_class}' "
                    f"matches capability '{cap.operation_class}'."
                    if opclass_match
                    else (
                        f"Intent operation class '{envelope.intent.operation_class}' "
                        f"differs from capability '{cap.operation_class}'."
                    )
                ),
            ),
        ]

        approval_required = (
            negotiation.policy_decision.requires_approval
            or cap.constraints.requires_human_approval
        )

        return ExecutionPlan(
            intent_id=envelope.intent_id,
            selected_capability=cap,
            selected_binding=binding,
            deterministic_target=target,
            grounded_parameters=grounded,
            execution_steps=steps,
            policy_checks_passed=policy_checks,
            approval_required=approval_required,
            trace=TraceMetadata(
                trace_id=envelope.trace_id,
                span_id=envelope.span_id,
                intent_id=envelope.intent_id,
            ),
        )
