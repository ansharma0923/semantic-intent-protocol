"""DecisionBundle – the complete output of the SIP pipeline.

A ``DecisionBundle`` is the top-level output produced by ``SIPPipeline.process``.
It bundles all four pipeline outputs into a single immutable object:

1. ``normalized_intent`` – the canonical internal intent produced by normalization.
2. ``policy_result`` – the policy decision (allow/deny + allowed capabilities).
3. ``execution_plan`` – the deterministic execution plan (None if denied).
4. ``audit_record`` – the pre-execution audit artifact.

Architecture note
-----------------
The ``DecisionBundle`` is the hand-off point between the SIP control plane
and the execution layer.  The execution layer must:
  * Check ``policy_result.allowed`` before executing.
  * Use ``execution_plan`` as the deterministic execution specification.
  * Persist ``audit_record`` to an append-only audit log.
  * Never execute if ``execution_plan`` is None.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field

from sip.core.normalized_intent import NormalizedIntent
from sip.negotiation.planner import ExecutionPlan
from sip.observability.audit import AuditRecord
from sip.policy.interface import PolicyResult


class DecisionBundle(BaseModel):
    """Complete output of the SIP pre-execution pipeline.

    Fields
    ------
    normalized_intent
        The canonical internal normalized intent.
    policy_result
        The policy decision produced by the canonical policy engine.
    execution_plan
        The deterministic execution plan.  ``None`` when the intent was
        denied, validation failed, or no safe plan could be produced.
    audit_record
        Pre-execution audit artifact.  **Always present**, including when
        the intent was denied.
    denied
        Convenience flag.  True when the policy denied the intent or no
        execution plan could be produced.
    metadata
        Arbitrary additional metadata attached by the pipeline.
    """

    normalized_intent: NormalizedIntent = Field(
        description="Canonical internal normalized intent."
    )
    policy_result: PolicyResult = Field(
        description="Policy decision."
    )
    execution_plan: ExecutionPlan | None = Field(
        default=None,
        description="Deterministic execution plan; None when denied.",
    )
    audit_record: AuditRecord = Field(
        description="Pre-execution audit artifact (always present).",
    )
    denied: bool = Field(
        default=False,
        description="True when the intent was denied or no plan could be produced.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Arbitrary additional pipeline metadata.",
    )

    @property
    def allowed(self) -> bool:
        """Convenience property: True when the intent may proceed."""
        return not self.denied and self.execution_plan is not None

    model_config = {"frozen": True}
