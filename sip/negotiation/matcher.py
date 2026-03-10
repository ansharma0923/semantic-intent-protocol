"""Capability matcher for SIP negotiation.

The matcher takes an IntentEnvelope and queries the registry to produce a
ranked list of candidate capabilities. All matching is deterministic.
"""

from __future__ import annotations

from sip.envelope.models import BindingType, IntentEnvelope
from sip.negotiation.results import NegotiationResult, PolicyDecisionSummary, RankedCandidate
from sip.registry.models import CapabilityDescriptor
from sip.registry.service import CapabilityRegistryService


def _build_rationale(
    cap: CapabilityDescriptor,
    score: float,
    envelope: IntentEnvelope,
) -> str:
    """Build a human-readable rationale string for a ranked candidate."""
    parts: list[str] = []

    intent_name = envelope.intent.intent_name.lower()
    if intent_name == cap.capability_id.lower():
        parts.append("exact intent name match")
    elif intent_name in cap.capability_id.lower() or intent_name in cap.name.lower():
        parts.append("partial intent name match")

    if envelope.intent.intent_domain.lower() in [d.lower() for d in cap.intent_domains]:
        parts.append("domain match")

    if cap.operation_class == envelope.intent.operation_class:
        parts.append("operation class match")

    preferred = _select_preferred_binding(envelope, cap)
    if preferred:
        parts.append(f"supports preferred binding '{preferred}'")

    parts.append(f"score={score:.1f}")
    return "; ".join(parts) if parts else f"score={score:.1f}"


def _select_preferred_binding(
    envelope: IntentEnvelope,
    cap: CapabilityDescriptor,
) -> BindingType | None:
    """Select the best binding for this capability given the envelope hints."""
    # Use the first preferred binding from the envelope that the capability supports
    for pb in envelope.protocol_bindings:
        if pb.binding_type in cap.supported_bindings:
            return pb.binding_type
    # Fallback: first capability binding from capability requirements
    for req in envelope.capability_requirements:
        if req.preferred_binding and req.preferred_binding in cap.supported_bindings:
            return req.preferred_binding
    # Fallback: first supported binding of the capability
    if cap.supported_bindings:
        return cap.supported_bindings[0]
    return None


class CapabilityMatcher:
    """Matches an IntentEnvelope to registered capabilities using the registry.

    Uses deterministic scoring; does not make LLM calls or probabilistic
    decisions. Integrates with the policy engine for trust/scope checks.
    """

    def __init__(self, registry: CapabilityRegistryService) -> None:
        self._registry = registry

    def match(self, envelope: IntentEnvelope) -> NegotiationResult:
        """Match an intent envelope against the registry.

        Args:
            envelope: The intent to match.

        Returns:
            A NegotiationResult with ranked candidates and a preliminary
            policy decision. The selected_capability is set only when a
            clear best match exists (score gap ≥ 1.0 over second best).
            Otherwise, requires_clarification is set.
        """
        preferred_binding: BindingType | None = None
        if envelope.protocol_bindings:
            preferred_binding = envelope.protocol_bindings[0].binding_type

        candidate_ids = list(envelope.negotiation.candidate_capabilities)

        ranked = self._registry.find_matches(
            intent_name=envelope.intent.intent_name,
            intent_domain=envelope.intent.intent_domain,
            operation_class=envelope.intent.operation_class,
            actor_trust=envelope.actor.trust_level,
            preferred_binding=preferred_binding,
            candidate_ids=candidate_ids or None,
            max_results=envelope.negotiation.max_candidates,
        )

        ranked_candidates = [
            RankedCandidate(
                capability=cap,
                score=score,
                rationale=_build_rationale(cap, score, envelope),
            )
            for cap, score in ranked
        ]

        # Determine if we have a clear winner
        selected_capability: CapabilityDescriptor | None = None
        selected_binding: BindingType | None = None
        selection_rationale = ""
        requires_clarification = False
        clarification_questions: list[str] = []

        if not ranked_candidates:
            requires_clarification = True
            clarification_questions.append(
                f"No capabilities found matching intent "
                f"'{envelope.intent.intent_name}' in domain "
                f"'{envelope.intent.intent_domain}'. "
                "Please refine your intent or check registered capabilities."
            )
        elif len(ranked_candidates) == 1:
            best = ranked_candidates[0]
            selected_capability = best.capability
            selected_binding = _select_preferred_binding(envelope, best.capability)
            selection_rationale = best.rationale
        else:
            best = ranked_candidates[0]
            second = ranked_candidates[1]
            gap = best.score - second.score

            if gap >= 1.0:
                # Clear winner
                selected_capability = best.capability
                selected_binding = _select_preferred_binding(envelope, best.capability)
                selection_rationale = best.rationale
            elif envelope.negotiation.allow_fallback:
                # Take the top candidate but note ambiguity
                selected_capability = best.capability
                selected_binding = _select_preferred_binding(envelope, best.capability)
                selection_rationale = (
                    f"{best.rationale} (selected as top candidate; "
                    f"gap to second={gap:.1f})"
                )
            else:
                requires_clarification = True
                clarification_questions.append(
                    f"Multiple capabilities match: "
                    f"{[c.capability.capability_id for c in ranked_candidates[:3]]}. "
                    "Please specify which capability you intend to use."
                )

        # Build allowed bindings
        allowed_bindings: list[BindingType] = []
        if selected_capability:
            for b in selected_capability.supported_bindings:
                if not envelope.protocol_bindings or any(
                    pb.binding_type == b for pb in envelope.protocol_bindings
                ):
                    allowed_bindings.append(b)
            # If no protocol_bindings were specified, all supported bindings are allowed
            if not envelope.protocol_bindings:
                allowed_bindings = list(selected_capability.supported_bindings)

        policy_decision = PolicyDecisionSummary(
            allowed=not requires_clarification or len(ranked_candidates) > 0,
            requires_approval=False,  # Will be enriched by the policy engine
            policy_notes=[],
        )

        return NegotiationResult(
            intent_id=envelope.intent_id,
            ranked_candidates=ranked_candidates,
            selected_capability=selected_capability,
            selection_rationale=selection_rationale,
            requires_clarification=requires_clarification,
            clarification_questions=clarification_questions,
            allowed_bindings=allowed_bindings,
            selected_binding=selected_binding,
            policy_decision=policy_decision,
        )
