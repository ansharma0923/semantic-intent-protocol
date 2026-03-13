"""Example: LLM-Proposed Intent.

This example illustrates the architecture pattern where an AI agent or LLM
proposes an IntentEnvelope, and the SIP control plane performs deterministic
validation, authorization, and execution planning.

Architecture:
    User
      ↓
    AI Agent / LLM  (simulated — no real LLM call)
      ↓
    IntentEnvelope  (constructed to represent an LLM-generated proposal)
      ↓
    SIP Control Plane
      ├─ Envelope Validation
      ├─ Capability Negotiation
      ├─ Policy Evaluation
      └─ ExecutionPlan
      ↓
    Execution Systems (outside SIP)
      REST | gRPC | MCP | A2A | RAG

SIP does not perform LLM inference. SIP acts as a deterministic control plane
responsible for validation, capability negotiation, authorization, and
execution planning. The LLM step shown here is a simulation only.

Run with:
    python examples/llm_proposed_intent.py
"""

from __future__ import annotations

import json
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sip.broker.service import BrokerService
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    NegotiationHints,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


def simulate_llm_intent_proposal(natural_language_request: str) -> IntentEnvelope:
    """Simulate an LLM proposing an IntentEnvelope from a natural language request.

    In a real system, an LLM or AI agent would translate the user's request into
    a structured IntentEnvelope. Here we construct the envelope directly to
    demonstrate what that proposal would look like — no real LLM is called.

    Args:
        natural_language_request: The original user request in natural language.

    Returns:
        A structured IntentEnvelope representing the LLM-generated proposal.
    """
    # NOTE: In production, this envelope would be constructed by an LLM or AI
    # agent outside the SIP protocol layer. SIP receives the structured
    # IntentEnvelope and performs deterministic validation and planning from here.
    return IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="llm-agent-001",
            actor_type=ActorType.AI_AGENT,
            name="LLM Proposer Agent",
            trust_level=TrustLevel.INTERNAL,
            scopes=["sip:knowledge:read"],
        ),
        target=TargetDescriptor(
            target_type=TargetType.CAPABILITY,
            namespace="knowledge_management",
        ),
        intent=IntentPayload(
            intent_name="retrieve_document",
            intent_domain="knowledge_management",
            operation_class=OperationClass.RETRIEVE,
            # natural_language_hint is stored for audit purposes only — never executed
            natural_language_hint=natural_language_request,
            parameters={
                "query": "approved architecture document",
                "collection": "architecture",
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Retrieve the latest approved architecture document.",
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.RAG),
            ProtocolBinding(binding_type=BindingType.REST),
        ],
        negotiation=NegotiationHints(
            candidate_capabilities=["retrieve_document"],
            allow_fallback=True,
        ),
    )


def main() -> None:
    # --- Setup ---
    registry = CapabilityRegistryService()
    seed_registry(registry)
    broker = BrokerService(registry=registry)

    print("=" * 70)
    print("SIP Example: LLM-Proposed Intent")
    print("=" * 70)

    # -----------------------------------------------------------------------
    # Step 1: Natural language request from the user
    # -----------------------------------------------------------------------
    user_request = "Show me the latest approved architecture document."
    print(f"\n[User Request]")
    print(f"  \"{user_request}\"")

    # -----------------------------------------------------------------------
    # Step 2: AI agent / LLM proposes an IntentEnvelope (simulated)
    # -----------------------------------------------------------------------
    print(f"\n[LLM Step — Simulated, no real LLM call]")
    print(f"  LLM translates the natural language request into a structured")
    print(f"  IntentEnvelope. This step occurs outside the SIP protocol layer.")

    # The envelope represents an LLM-generated proposal
    envelope = simulate_llm_intent_proposal(user_request)
    print(f"\n  Proposed IntentEnvelope:")
    print(f"    intent_name:   {envelope.intent.intent_name}")
    print(f"    intent_domain: {envelope.intent.intent_domain}")
    print(f"    operation:     {envelope.intent.operation_class}")
    print(f"    parameters:    {json.dumps(envelope.intent.parameters, indent=4)}")
    print(f"    nl_hint:       \"{envelope.intent.natural_language_hint}\"")
    print(f"                   (stored for audit only — never executed by SIP)")

    # -----------------------------------------------------------------------
    # Step 3: SIP broker processes the envelope deterministically
    # -----------------------------------------------------------------------
    print(f"\n[SIP Broker — Deterministic Processing]")
    print(f"  SIP validates, negotiates, and authorizes the proposed envelope.")

    result, translation = broker.translate(envelope)

    print(f"\n[Negotiation Result]")
    if result.negotiation_result and result.negotiation_result.selected_capability:
        nr = result.negotiation_result
        print(f"  Selected Capability: {nr.selected_capability.capability_id}")
        print(f"  Selected Binding:    {nr.selected_binding}")
        print(f"  Rationale:           {nr.selection_rationale}")

    print(f"\n[Policy Decision]")
    if result.negotiation_result:
        pd = result.negotiation_result.policy_decision
        print(f"  Allowed:           {pd.allowed}")
        print(f"  Requires Approval: {pd.requires_approval}")
        for note in pd.policy_notes:
            print(f"  Note: {note}")

    print(f"\n[Execution Plan]")
    if result.execution_plan:
        plan = result.execution_plan
        print(f"  Plan ID:    {plan.plan_id}")
        print(f"  Capability: {plan.selected_capability.capability_id}")
        print(f"  Binding:    {plan.selected_binding}")
        print(f"  Parameters: {json.dumps(plan.grounded_parameters, indent=4)}")
        print(f"  Approval:   {plan.approval_required}")

    if translation:
        print(f"\n[Translation ({translation.binding_type.value})]")
        print(json.dumps(translation.payload, indent=2))

    print(f"\n[Audit Record]")
    ar = result.audit_record
    print(f"  Intent ID: {ar.intent_id}")
    print(f"  Trace ID:  {ar.trace_id}")
    print(f"  Outcome:   {ar.outcome_summary}")
    print(f"  Action:    {ar.action_taken}")
    print(f"  Policy:    {'allowed' if ar.policy_allowed else 'denied'}")

    print(f"\n[Architecture Summary]")
    print(f"  SIP Pipeline Deterministic: True")
    print(
        "  Note: SIP execution planning is deterministic. "
        "AI or LLM systems may generate intents outside the protocol layer."
    )
    print()


if __name__ == "__main__":
    main()
