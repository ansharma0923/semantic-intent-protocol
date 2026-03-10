"""RAG (Retrieval-Augmented Generation) adapter for SIP.

Translates an ExecutionPlan into a retrieval query specification:
collection/source, query, filters, and result contract. Does not
perform actual retrieval.
"""

from __future__ import annotations

from typing import Any

from sip.envelope.models import BindingType
from sip.negotiation.planner import ExecutionPlan
from sip.translator.base import BaseAdapter, TranslationResult


class RagAdapter(BaseAdapter):
    """Translates an ExecutionPlan into a RAG retrieval specification.

    The generated payload contains:
      - ``collection``: Data source or collection name
      - ``retrieval_query``: The structured retrieval query
      - ``filters``: Key-value filters to apply
      - ``result_contract``: Expected result format and constraints

    No actual retrieval calls are made.
    """

    @property
    def binding_type(self) -> BindingType:
        return BindingType.RAG

    def translate(self, plan: ExecutionPlan) -> TranslationResult:
        """Translate the plan into a RAG retrieval specification."""
        self._require_binding(plan)

        cap = plan.selected_capability
        capability_id = cap.capability_id
        provider_id = cap.provider.provider_id
        params = plan.grounded_parameters

        # Derive collection from capability or explicit parameter
        collection = params.get(
            "collection",
            params.get("source", self._default_collection(capability_id)),
        )

        # Build retrieval query from intent parameters
        retrieval_query = self._build_retrieval_query(params)

        # Build filters from remaining parameters
        filters: dict[str, Any] = {
            k: v
            for k, v in params.items()
            if k not in ("collection", "source", "query", "text")
            and not isinstance(v, (dict, list))
        }

        # Result contract specifies what form the output should take
        result_contract: dict[str, Any] = {
            "output_format": params.get("output_format", "json"),
            "max_results": params.get("max_results", 10),
            "include_metadata": params.get("include_metadata", True),
            "output_schema": cap.output_schema.description,
        }

        payload: dict[str, Any] = {
            "collection": collection,
            "retrieval_query": retrieval_query,
            "filters": filters,
            "result_contract": result_contract,
            "trace": {
                "trace_id": plan.trace.trace_id,
                "span_id": plan.trace.span_id,
                "intent_id": plan.intent_id,
            },
        }

        return TranslationResult(
            binding_type=BindingType.RAG,
            payload=payload,
            metadata={
                "capability_id": capability_id,
                "provider_id": provider_id,
            },
        )

    @staticmethod
    def _default_collection(capability_id: str) -> str:
        """Derive a sensible default collection name from the capability ID."""
        return capability_id.replace("_", "-") + "-store"

    @staticmethod
    def _build_retrieval_query(params: dict[str, Any]) -> str:
        """Build a retrieval query string from parameters.

        Raises:
            ValueError: If no recognizable query parameter is present.
                A RAG retrieval must have an explicit query to remain
                deterministic; silently producing a vague query violates
                the SIP determinism principle.
        """
        if "query" in params:
            return str(params["query"])
        if "text" in params:
            return str(params["text"])
        if "topic" in params:
            return str(params["topic"])
        # Collect all string values as a last resort
        parts = [str(v) for v in params.values() if isinstance(v, str)]
        if parts:
            return " ".join(parts)
        raise ValueError(
            "RAG adapter requires at least one of 'query', 'text', or 'topic' "
            "parameters to produce a deterministic retrieval query. "
            "Refusing to produce a vague fallback query."
        )
