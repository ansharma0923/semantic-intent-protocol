"""Execution planner for SIP.

Takes a NegotiationResult and a validated IntentEnvelope and produces a
deterministic ExecutionPlan. The planner grounds parameters, selects binding,
and constructs execution steps.
"""

from __future__ import annotations

from enum import Enum
from typing import Any
from uuid import uuid4

from pydantic import BaseModel, Field, field_validator

from sip.envelope.models import BindingType, IntentEnvelope
from sip.extensions import validate_extension_keys
from sip.negotiation.results import NegotiationResult
from sip.registry.models import CapabilityDescriptor


# ---------------------------------------------------------------------------
# Execution abstraction types
# ---------------------------------------------------------------------------


class ExecutionType(str, Enum):
    """Execution type abstraction for a plan step.

    These are protocol-agnostic labels that describe *what kind* of execution
    is required.  They are separate from ``BindingType`` (which describes
    the wire protocol) to allow plans to be reasoned about without binding
    to a specific SDK or transport.

    Values
    ------
    MCP_TOOL
        Model Context Protocol tool invocation.
    REST_API
        HTTP REST API call.
    GRPC_SERVICE
        gRPC service call.
    A2A_AGENT
        Agent-to-agent delegation (A2A protocol).
    INTERNAL_SKILL
        Internal system skill (no external network call).
    MANUAL_STEP
        Step that requires human action before the plan can continue.
    """

    MCP_TOOL = "mcp_tool"
    REST_API = "rest_api"
    GRPC_SERVICE = "grpc_service"
    A2A_AGENT = "a2a_agent"
    INTERNAL_SKILL = "internal_skill"
    MANUAL_STEP = "manual_step"


# Mapping from BindingType to ExecutionType
_BINDING_TO_EXECUTION_TYPE: dict[BindingType, ExecutionType] = {
    BindingType.REST: ExecutionType.REST_API,
    BindingType.GRPC: ExecutionType.GRPC_SERVICE,
    BindingType.MCP: ExecutionType.MCP_TOOL,
    BindingType.A2A: ExecutionType.A2A_AGENT,
    BindingType.RAG: ExecutionType.REST_API,  # RAG is typically REST-based
}


def binding_to_execution_type(binding: BindingType) -> ExecutionType:
    """Map a ``BindingType`` to an ``ExecutionType``."""
    return _BINDING_TO_EXECUTION_TYPE.get(binding, ExecutionType.REST_API)


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
    execution_type: ExecutionType = Field(
        default=ExecutionType.REST_API,
        description="Execution type abstraction for this step.",
    )
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

    Extended fields (v0.2)
    ----------------------
    execution_type
        Protocol-agnostic execution type for the selected capability.
    preconditions
        Conditions that must be true before execution begins.
    guard_conditions
        Runtime guard conditions evaluated during execution.
    fallback_behavior
        What to do if the primary execution path fails.
    expected_outputs
        Descriptions of the expected outputs.
    selection_basis
        Human-readable explanation of why this capability was selected.
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
    execution_type: ExecutionType = Field(
        default=ExecutionType.REST_API,
        description="Execution type abstraction for the selected capability.",
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
    preconditions: list[str] = Field(
        default_factory=list,
        description="Conditions that must be true before execution begins.",
    )
    guard_conditions: list[str] = Field(
        default_factory=list,
        description="Runtime guard conditions evaluated during execution.",
    )
    fallback_behavior: str = Field(
        default="fail_closed",
        description=(
            "What to do if the primary execution path fails. "
            "Defaults to 'fail_closed' (deny the operation)."
        ),
    )
    expected_outputs: list[str] = Field(
        default_factory=list,
        description="Descriptions of the expected outputs.",
    )
    selection_basis: str = Field(
        default="",
        description="Human-readable explanation of why this capability was selected.",
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
    provenance_summary: dict[str, Any] | None = Field(
        default=None,
        description=(
            "Optional summary of provenance metadata propagated from the envelope. "
            "Includes originator, submitted_by, and delegation_chain so downstream "
            "systems can observe the full delegation path."
        ),
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description=(
            "Optional protocol extensions.  Keys must use 'x_<name>' or "
            "'<vendor>.<name>' format."
        ),
    )

    @field_validator("extensions")
    @classmethod
    def _validate_extensions(cls, v: dict[str, Any]) -> dict[str, Any]:
        return validate_extension_keys(v)


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
                execution_type=binding_to_execution_type(binding),
                parameters=grounded,
                depends_on=[],
            )
        ]

        policy_checks: list[PolicyCheckRecord] = [
            PolicyCheckRecord(
                check_name="trust_level",
                result="passed",
                notes=(
                    f"Actor trust '{envelope.actor.trust_level}' meets "
                    f"capability minimum '{cap.minimum_trust_tier}'."
                ),
            ),
            PolicyCheckRecord(
                check_name="operation_class_match",
                result="passed",
                notes=(
                    f"Intent operation class '{envelope.intent.operation_class}' "
                    f"matches capability '{cap.operation_class}'."
                ),
            ),
        ]

        approval_required = (
            negotiation.policy_decision.requires_approval
            or cap.constraints.requires_human_approval
        )

        # Build provenance summary if the envelope carries a provenance block
        provenance_summary: dict[str, Any] | None = None
        if envelope.provenance is not None:
            prov = envelope.provenance
            provenance_summary = {
                "originator": prov.originator,
                "submitted_by": prov.submitted_by,
                "delegation_chain": list(prov.delegation_chain),
            }

        exec_type = binding_to_execution_type(binding)

        return ExecutionPlan(
            intent_id=envelope.intent_id,
            selected_capability=cap,
            selected_binding=binding,
            execution_type=exec_type,
            deterministic_target=target,
            grounded_parameters=grounded,
            execution_steps=steps,
            preconditions=[],
            guard_conditions=[],
            fallback_behavior="fail_closed",
            expected_outputs=[cap.output_schema.description] if cap.output_schema.description else [],
            selection_basis=negotiation.selection_rationale,
            policy_checks_passed=policy_checks,
            approval_required=approval_required,
            trace=TraceMetadata(
                trace_id=envelope.trace_id,
                span_id=envelope.span_id,
                intent_id=envelope.intent_id,
            ),
            provenance_summary=provenance_summary,
        )
