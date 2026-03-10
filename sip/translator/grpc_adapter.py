"""gRPC adapter for SIP.

Translates an ExecutionPlan into a gRPC call specification (service name,
method name, request message dict). Does not make actual gRPC calls.
"""

from __future__ import annotations

from typing import Any

from sip.envelope.models import BindingType
from sip.negotiation.planner import ExecutionPlan
from sip.translator.base import BaseAdapter, TranslationResult


class GrpcAdapter(BaseAdapter):
    """Translates an ExecutionPlan into a gRPC call specification.

    The generated payload contains:
      - ``service_name``: Fully qualified gRPC service name
      - ``method_name``: RPC method name
      - ``request_message``: Request message as a dict
      - ``metadata``: gRPC metadata (call headers)

    No actual gRPC calls are made.
    """

    @property
    def binding_type(self) -> BindingType:
        return BindingType.GRPC

    def translate(self, plan: ExecutionPlan) -> TranslationResult:
        """Translate the plan into a gRPC call specification."""
        self._require_binding(plan)

        cap = plan.selected_capability
        provider_id = cap.provider.provider_id
        capability_id = cap.capability_id

        # Derive service and method names from capability metadata
        service_name = self._build_service_name(provider_id, capability_id)
        method_name = self._build_method_name(capability_id)

        # gRPC metadata (analogous to HTTP headers)
        grpc_metadata: list[tuple[str, str]] = [
            ("x-sip-trace-id", plan.trace.trace_id),
            ("x-sip-span-id", plan.trace.span_id),
            ("x-sip-intent-id", plan.intent_id),
        ]

        request_message: dict[str, Any] = dict(plan.grounded_parameters)

        payload: dict[str, Any] = {
            "service_name": service_name,
            "method_name": method_name,
            "request_message": request_message,
            "grpc_metadata": grpc_metadata,
        }

        return TranslationResult(
            binding_type=BindingType.GRPC,
            payload=payload,
            metadata={
                "capability_id": capability_id,
                "provider_id": provider_id,
            },
        )

    @staticmethod
    def _build_service_name(provider_id: str, capability_id: str) -> str:
        """Derive a fully qualified gRPC service name."""
        # Converts e.g. "network_ops" + "diagnose_network_issue" →
        # "sip.network_ops.DiagnoseNetworkIssueService"
        service = "".join(
            part.capitalize() for part in capability_id.split("_")
        ) + "Service"
        return f"sip.{provider_id}.{service}"

    @staticmethod
    def _build_method_name(capability_id: str) -> str:
        """Derive a gRPC method name from capability_id."""
        # Converts "diagnose_network_issue" → "DiagnoseNetworkIssue"
        return "".join(part.capitalize() for part in capability_id.split("_"))
