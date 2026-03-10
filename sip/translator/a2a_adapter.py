"""A2A (Agent-to-Agent) adapter for SIP.

Translates an ExecutionPlan into an A2A task delegation payload. Does not
make actual inter-agent calls.
"""

from __future__ import annotations

from typing import Any

from sip.envelope.models import BindingType
from sip.negotiation.planner import ExecutionPlan
from sip.translator.base import BaseAdapter, TranslationResult


class A2aAdapter(BaseAdapter):
    """Translates an ExecutionPlan into an A2A task delegation payload.

    The generated payload contains:
      - ``agent_task_type``: Task type identifier
      - ``target_agent``: Target agent identifier
      - ``task_payload``: Structured task content
      - ``delegation_context``: Metadata about the delegation

    No actual agent calls are made.
    """

    @property
    def binding_type(self) -> BindingType:
        return BindingType.A2A

    def translate(self, plan: ExecutionPlan) -> TranslationResult:
        """Translate the plan into an A2A task delegation payload."""
        self._require_binding(plan)

        cap = plan.selected_capability
        provider_id = cap.provider.provider_id
        capability_id = cap.capability_id

        agent_task_type = capability_id
        target_agent = provider_id

        task_payload: dict[str, Any] = {
            "task_type": agent_task_type,
            "parameters": dict(plan.grounded_parameters),
            "capability_id": capability_id,
            "desired_output": cap.output_schema.description,
        }

        delegation_context: dict[str, Any] = {
            "trace_id": plan.trace.trace_id,
            "span_id": plan.trace.span_id,
            "intent_id": plan.intent_id,
            "delegating_plan_id": plan.plan_id,
            "approval_required": plan.approval_required,
        }

        payload: dict[str, Any] = {
            "agent_task_type": agent_task_type,
            "target_agent": target_agent,
            "task_payload": task_payload,
            "delegation_context": delegation_context,
        }

        return TranslationResult(
            binding_type=BindingType.A2A,
            payload=payload,
            metadata={
                "capability_id": capability_id,
                "provider_id": provider_id,
            },
        )
