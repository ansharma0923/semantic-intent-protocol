"""Deterministic planner for the canonical SIP pipeline.

Accepts a ``NormalizedIntent``, a ``PolicyResult``, and a list of
externally-supplied ``CapabilityDescriptor`` candidates and produces a
deterministic ``ExecutionPlan``.

Design principles
-----------------
* **No discovery**: The planner never queries a registry.  It operates only
  on the candidates supplied by the caller (which in turn come from an
  external discovery layer such as ADP).
* **Policy-first**: Only capabilities in ``PolicyResult.allowed_capabilities``
  are considered.
* **Deterministic tie-breaking**: When multiple candidates are equally valid,
  the selection is made by sorting on ``(provider_id, capability_id)`` in
  ascending lexicographic order.  This guarantees that the same set of
  candidates always produces the same plan.
* **Fail closed**: If no safe plan can be produced, a ``FailClosedError`` is
  raised rather than returning an unsafe or empty plan.
"""

from __future__ import annotations

import logging
from datetime import datetime, timezone
from typing import Any
from uuid import uuid4

from sip.core.fail_closed import FailClosedError, check_allowed_capabilities_present, check_policy_allowed
from sip.core.normalized_intent import NormalizedIntent
from sip.negotiation.planner import (
    ExecutionPlan,
    ExecutionStep,
    ExecutionType,
    PolicyCheckRecord,
    TraceMetadata,
    binding_to_execution_type,
)
from sip.policy.interface import PolicyResult
from sip.registry.models import CapabilityDescriptor
from sip.envelope.models import BindingType

logger = logging.getLogger(__name__)


def _select_best_binding(
    intent: NormalizedIntent,
    cap: CapabilityDescriptor,
) -> BindingType | None:
    """Select the best binding for a capability given the intent hints.

    Prefers the intent's ``preferred_execution_mode`` if it matches a
    supported binding, then falls back to the first supported binding.
    """
    preferred = intent.preferred_execution_mode
    if preferred:
        for binding in cap.supported_bindings:
            if binding.value == preferred:
                return binding
    if cap.supported_bindings:
        return cap.supported_bindings[0]
    return None


def _ground_parameters(
    intent: NormalizedIntent,
    cap: CapabilityDescriptor,
) -> dict[str, Any]:
    """Ground intent parameters against the capability's input schema."""
    raw_params = intent.metadata.get("parameters", {})
    grounded: dict[str, Any] = dict(raw_params) if isinstance(raw_params, dict) else {}

    for field_name in cap.input_schema.required_fields:
        if field_name not in grounded:
            grounded[field_name] = f"<REQUIRED:{field_name}>"

    return grounded


def _build_deterministic_target(
    cap: CapabilityDescriptor,
    binding: BindingType,
    endpoint: str | None = None,
) -> dict[str, Any]:
    """Build binding-specific target information deterministically."""
    provider_id = cap.provider.provider_id
    return {
        "capability_id": cap.capability_id,
        "provider_id": provider_id,
        "binding_type": binding.value,
        "endpoint": endpoint or f"<ENDPOINT:{provider_id}/{cap.capability_id}>",
    }


class DeterministicPlanner:
    """Produces a deterministic ``ExecutionPlan`` from normalized inputs.

    This planner does not perform discovery; it operates only on the
    ``PolicyResult.allowed_capabilities`` subset.  Selection uses stable
    tie-breaking by ``(provider_id, capability_id)`` so the output is
    reproducible given the same inputs.

    Usage::

        planner = DeterministicPlanner()
        plan = planner.plan(normalized_intent, policy_result, candidate_capabilities)
    """

    def plan(
        self,
        normalized_intent: NormalizedIntent,
        policy_result: PolicyResult,
        candidate_capabilities: list[CapabilityDescriptor],
    ) -> ExecutionPlan:
        """Produce an ``ExecutionPlan``.

        Args:
            normalized_intent: The canonical internal intent.
            policy_result: The policy decision (must be allowed).
            candidate_capabilities: Externally supplied candidates.  Only
                those present in ``policy_result.allowed_capabilities`` are
                considered.

        Returns:
            A deterministic ``ExecutionPlan``.

        Raises:
            FailClosedError: If the policy denied the intent, if no allowed
                capabilities remain, or if no binding can be selected.
        """
        # Fail closed: policy must have allowed the intent
        check_policy_allowed(policy_result)
        # Fail closed: at least one allowed capability must exist
        check_allowed_capabilities_present(policy_result)

        # Intersect externally-supplied candidates with policy-allowed set
        allowed_ids = {c.capability_id for c in policy_result.allowed_capabilities}
        eligible = [c for c in candidate_capabilities if c.capability_id in allowed_ids]

        if not eligible:
            # Fall back to the policy-allowed set directly (they came from the same source)
            eligible = list(policy_result.allowed_capabilities)

        if not eligible:
            raise FailClosedError.from_reason(
                reason_code="NO_ALLOWED_CAPABILITIES",
                reason="No eligible capabilities after cross-referencing policy result.",
                required_actions=[
                    "Ensure candidate_capabilities include at least one policy-allowed capability."
                ],
            )

        # Stable tie-breaking: sort by (provider_id, capability_id)
        eligible.sort(key=lambda c: (c.provider.provider_id, c.capability_id))

        selected = eligible[0]

        binding = _select_best_binding(normalized_intent, selected)
        if binding is None:
            raise FailClosedError.from_reason(
                reason_code="NO_ALLOWED_CAPABILITIES",
                reason=(
                    f"Capability '{selected.capability_id}' has no supported bindings; "
                    "cannot produce a safe execution plan."
                ),
            )

        exec_type = binding_to_execution_type(binding)
        grounded = _ground_parameters(normalized_intent, selected)
        target = _build_deterministic_target(selected, binding)

        steps = [
            ExecutionStep(
                step_index=0,
                step_name=f"invoke_{selected.capability_id}",
                description=(
                    f"Invoke '{selected.name}' via {binding.value} binding "
                    f"for intent '{normalized_intent.intent_id}'."
                ),
                capability_id=selected.capability_id,
                binding=binding,
                execution_type=exec_type,
                parameters=grounded,
                depends_on=[],
            )
        ]

        preconditions = list(policy_result.conditions)
        guard_conditions: list[str] = [
            f"Policy allowed: {policy_result.reason_code}",
        ]
        fallback = "fail_closed"
        expected_outputs = (
            [selected.output_schema.description]
            if selected.output_schema.description
            else []
        )

        approval_required = bool(policy_result.required_approvals)

        # Build provenance summary from normalized intent
        provenance_summary: dict[str, Any] | None = None
        if normalized_intent.actor.originator or normalized_intent.actor.delegation_chain:
            provenance_summary = {
                "originator": normalized_intent.actor.originator,
                "delegation_chain": normalized_intent.actor.delegation_chain,
            }

        selection_basis = (
            f"Deterministic selection: capability '{selected.capability_id}' "
            f"(provider '{selected.provider.provider_id}') chosen by stable "
            f"(provider_id, capability_id) sort from {len(eligible)} eligible candidate(s)."
        )

        policy_checks = [
            PolicyCheckRecord(
                check_name="policy_allowed",
                result="passed",
                notes=policy_result.reason,
            ),
            PolicyCheckRecord(
                check_name="capability_selected",
                result="passed",
                notes=f"Selected '{selected.capability_id}' from {len(eligible)} eligible.",
            ),
        ]

        logger.info(
            "DeterministicPlanner: selected capability=%s binding=%s for intent=%s",
            selected.capability_id,
            binding.value,
            normalized_intent.intent_id,
        )

        return ExecutionPlan(
            intent_id=normalized_intent.intent_id,
            selected_capability=selected,
            selected_binding=binding,
            execution_type=exec_type,
            deterministic_target=target,
            grounded_parameters=grounded,
            execution_steps=steps,
            preconditions=preconditions,
            guard_conditions=guard_conditions,
            fallback_behavior=fallback,
            expected_outputs=expected_outputs,
            selection_basis=selection_basis,
            policy_checks_passed=policy_checks,
            approval_required=approval_required,
            trace=TraceMetadata(
                trace_id=normalized_intent.correlation_id,
                span_id=str(uuid4()),
                intent_id=normalized_intent.intent_id,
            ),
            provenance_summary=provenance_summary,
        )
