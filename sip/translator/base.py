"""Base adapter interface for SIP translators.

All execution protocol adapters extend BaseAdapter and implement ``translate``.
Adapters generate deterministic execution payloads from an ExecutionPlan —
they do not execute anything themselves.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from sip.envelope.models import BindingType
from sip.negotiation.planner import ExecutionPlan


class TranslationResult:
    """The output of an adapter's translate() call.

    Encapsulates the binding type, the generated payload, and any metadata
    that the executor will need.
    """

    def __init__(
        self,
        binding_type: BindingType,
        payload: dict[str, Any],
        metadata: dict[str, Any] | None = None,
    ) -> None:
        self.binding_type = binding_type
        self.payload = payload
        self.metadata = metadata or {}

    def __repr__(self) -> str:
        return (
            f"TranslationResult(binding={self.binding_type.value}, "
            f"payload_keys={list(self.payload.keys())})"
        )


class BaseAdapter(ABC):
    """Abstract base class for all SIP execution protocol adapters.

    Subclasses translate an ExecutionPlan into a binding-specific payload.
    No actual network calls are made here; adapters are pure translation units.
    """

    @property
    @abstractmethod
    def binding_type(self) -> BindingType:
        """The BindingType this adapter handles."""

    @abstractmethod
    def translate(self, plan: ExecutionPlan) -> TranslationResult:
        """Translate an ExecutionPlan into a binding-specific execution payload.

        Args:
            plan: The fully specified execution plan.

        Returns:
            A TranslationResult containing the deterministic payload.

        Raises:
            ValueError: If the plan's binding type does not match this adapter.
        """

    def _require_binding(self, plan: ExecutionPlan) -> None:
        """Assert that the plan's binding matches this adapter."""
        if plan.selected_binding != self.binding_type:
            raise ValueError(
                f"Adapter '{self.__class__.__name__}' handles "
                f"'{self.binding_type.value}' but plan has "
                f"'{plan.selected_binding.value}'."
            )
