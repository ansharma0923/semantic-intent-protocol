"""MCP (Model Context Protocol) adapter for SIP.

Translates an ExecutionPlan into an MCP tool invocation specification:
tool name, tool arguments, and an execution contract. Does not make
actual MCP calls.
"""

from __future__ import annotations

from typing import Any

from sip.envelope.models import BindingType
from sip.negotiation.planner import ExecutionPlan
from sip.translator.base import BaseAdapter, TranslationResult


class McpAdapter(BaseAdapter):
    """Translates an ExecutionPlan into an MCP tool invocation specification.

    The generated payload contains:
      - ``tool_name``: MCP tool name
      - ``tool_arguments``: Dict of tool arguments
      - ``execution_contract``: Describes expected input/output contract

    No actual MCP calls are made.
    """

    @property
    def binding_type(self) -> BindingType:
        return BindingType.MCP

    def translate(self, plan: ExecutionPlan) -> TranslationResult:
        """Translate the plan into an MCP tool invocation specification."""
        self._require_binding(plan)

        cap = plan.selected_capability
        capability_id = cap.capability_id

        tool_name = self._build_tool_name(capability_id)
        tool_arguments: dict[str, Any] = dict(plan.grounded_parameters)

        # Execution contract describes the input/output schema for the tool
        execution_contract: dict[str, Any] = {
            "input_schema": {
                "properties": cap.input_schema.properties,
                "required": cap.input_schema.required_fields,
            },
            "output_schema": {
                "description": cap.output_schema.description,
                "properties": cap.output_schema.properties,
            },
            "idempotent": cap.execution.idempotent,
            "supports_dry_run": cap.execution.supports_dry_run,
        }

        payload: dict[str, Any] = {
            "tool_name": tool_name,
            "tool_arguments": tool_arguments,
            "execution_contract": execution_contract,
            "trace": {
                "trace_id": plan.trace.trace_id,
                "span_id": plan.trace.span_id,
                "intent_id": plan.intent_id,
            },
        }

        return TranslationResult(
            binding_type=BindingType.MCP,
            payload=payload,
            metadata={
                "capability_id": capability_id,
                "provider_id": cap.provider.provider_id,
            },
        )

    @staticmethod
    def _build_tool_name(capability_id: str) -> str:
        """Map capability_id to an MCP tool name (kept as-is for MCP conventions)."""
        return capability_id
