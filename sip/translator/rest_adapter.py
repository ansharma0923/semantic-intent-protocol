"""REST adapter for SIP.

Translates an ExecutionPlan into an HTTP request payload (method, path,
headers, body, query parameters). Does not make network calls.
"""

from __future__ import annotations

from typing import Any

from sip.envelope.models import BindingType, OperationClass
from sip.negotiation.planner import ExecutionPlan
from sip.translator.base import BaseAdapter, TranslationResult

# Mapping from OperationClass to HTTP method
_OPERATION_TO_HTTP_METHOD: dict[OperationClass, str] = {
    OperationClass.READ: "GET",
    OperationClass.RETRIEVE: "GET",
    OperationClass.ANALYZE: "GET",
    OperationClass.WRITE: "POST",
    OperationClass.EXECUTE: "POST",
    OperationClass.DELEGATE: "POST",
}


class RestAdapter(BaseAdapter):
    """Translates an ExecutionPlan into an HTTP request specification.

    The generated payload contains:
      - ``method``: HTTP method derived from operation class
      - ``path``: Resource path derived from capability ID
      - ``headers``: Standard SIP trace headers
      - ``body``: Request body (for POST/PUT/PATCH)
      - ``query_params``: Query parameters (for GET)

    No actual HTTP calls are made.
    """

    @property
    def binding_type(self) -> BindingType:
        return BindingType.REST

    def translate(self, plan: ExecutionPlan) -> TranslationResult:
        """Translate the plan into an HTTP request payload."""
        self._require_binding(plan)

        cap = plan.selected_capability
        operation = cap.operation_class
        method = _OPERATION_TO_HTTP_METHOD.get(operation, "POST")
        endpoint = plan.deterministic_target.get("endpoint", "")

        # Build path: use endpoint if provided, else derive from capability_id
        path = self._build_path(cap.capability_id, endpoint)

        headers: dict[str, str] = {
            "Content-Type": "application/json",
            "Accept": "application/json",
            "X-SIP-Trace-Id": plan.trace.trace_id,
            "X-SIP-Span-Id": plan.trace.span_id,
            "X-SIP-Intent-Id": plan.intent_id,
        }

        body: dict[str, Any] = {}
        query_params: dict[str, Any] = {}

        if method in ("POST", "PUT", "PATCH"):
            body = dict(plan.grounded_parameters)
        else:
            # For GET, move parameters to query string
            query_params = {
                k: v
                for k, v in plan.grounded_parameters.items()
                if not isinstance(v, (dict, list))
            }

        payload: dict[str, Any] = {
            "method": method,
            "path": path,
            "headers": headers,
            "body": body,
            "query_params": query_params,
        }

        return TranslationResult(
            binding_type=BindingType.REST,
            payload=payload,
            metadata={
                "capability_id": cap.capability_id,
                "provider_id": cap.provider.provider_id,
                "operation_class": operation.value,
            },
        )

    @staticmethod
    def _build_path(capability_id: str, endpoint: str) -> str:
        """Build the resource path for the HTTP request."""
        # If we have a real endpoint, use it directly
        if endpoint and not endpoint.startswith("<ENDPOINT"):
            return endpoint
        # Derive path from capability_id (snake_case → /resource-name)
        slug = capability_id.replace("_", "-")
        return f"/api/v1/{slug}"
