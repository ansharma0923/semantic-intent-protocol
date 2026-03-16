"""
SIP Public Introduction Demo
=============================

This demo shows the complete SIP flow in ~30 lines of working code:

  1. Build an IntentEnvelope expressing a semantic intent
  2. Submit it to the SIP broker
  3. Receive a NegotiationResult and ExecutionPlan
  4. Inspect the audit record

No server required — the broker runs in-process.
No real network calls are made — SIP produces a deterministic plan
that an external execution system would carry out.

Run this demo:

    python examples/public_intro_demo.py

Prerequisites:

    pip install -e ".[dev]"
"""

from sip.broker.service import BrokerService
from sip.envelope.models import (
    ActorDescriptor,
    ActorType,
    BindingType,
    DesiredOutcome,
    IntentEnvelope,
    IntentPayload,
    OperationClass,
    ProtocolBinding,
    TargetDescriptor,
    TargetType,
    TrustLevel,
)
from sip.registry.bootstrap import build_seeded_registry


def main() -> None:
    print("=" * 60)
    print("  Semantic Intent Protocol (SIP) — Introduction Demo")
    print("=" * 60)

    # ----------------------------------------------------------------
    # Step 1: Build a SIP broker with a pre-seeded capability registry.
    # In production, capabilities are registered by the services that
    # implement them.
    # ----------------------------------------------------------------
    broker = BrokerService(registry=build_seeded_registry())
    print("\n[1] Broker ready with seeded capability registry.")

    # ----------------------------------------------------------------
    # Step 2: Build an IntentEnvelope.
    # The envelope expresses *what* the actor wants, not *how* to get it.
    # The broker resolves the how.
    # ----------------------------------------------------------------
    envelope = IntentEnvelope(
        actor=ActorDescriptor(
            actor_id="demo-agent-01",
            actor_type=ActorType.AI_AGENT,
            name="Demo Agent",
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
            parameters={
                "query": "SIP architecture overview",
                "top_k": 3,
            },
        ),
        desired_outcome=DesiredOutcome(
            summary="Retrieve the top-3 documents about SIP architecture.",
            output_format="json",
        ),
        protocol_bindings=[
            ProtocolBinding(binding_type=BindingType.RAG),
        ],
    )

    print(f"\n[2] IntentEnvelope built.")
    print(f"    intent_id  : {envelope.intent_id}")
    print(f"    actor      : {envelope.actor.actor_id} ({envelope.actor.trust_level.value})")
    print(f"    intent     : {envelope.intent.intent_name} ({envelope.intent.operation_class.value})")
    print(f"    binding    : {envelope.protocol_bindings[0].binding_type.value}")

    # ----------------------------------------------------------------
    # Step 3: Submit the envelope to the broker.
    # The broker runs the full control-plane pipeline:
    #   - schema validation
    #   - capability negotiation (match + rank)
    #   - policy evaluation (scopes, trust, risk)
    #   - execution planning (grounded parameters)
    #   - audit record generation
    # ----------------------------------------------------------------
    result = broker.handle(envelope)

    print("\n[3] Broker processed the intent.")

    # ----------------------------------------------------------------
    # Step 4: Inspect the NegotiationResult.
    # ----------------------------------------------------------------
    neg = result.negotiation_result
    print(f"\n[4] Negotiation result:")
    print(f"    selected capability : {neg.selected_capability.capability_id}")
    print(f"    selected binding    : {neg.selected_binding.value}")
    print(f"    policy allowed      : {neg.policy_decision.allowed}")
    if neg.policy_decision.policy_notes:
        print(f"    policy notes        : {neg.policy_decision.policy_notes[0]}")

    # ----------------------------------------------------------------
    # Step 5: Inspect the ExecutionPlan.
    # The plan is a deterministic, fully-specified specification ready
    # for the RAG adapter to execute. SIP does not make the call itself.
    # ----------------------------------------------------------------
    plan = result.execution_plan
    print(f"\n[5] Execution plan:")
    print(f"    plan_id          : {plan.plan_id}")
    print(f"    grounded_params  : {plan.grounded_parameters}")
    print(f"    steps            : {len(plan.execution_steps)}")
    step = plan.execution_steps[0]
    print(f"    step[0]          : {step.step_name} via {step.binding.value}")

    # ----------------------------------------------------------------
    # Step 6: Inspect the AuditRecord.
    # Every processed intent produces an immutable audit record.
    # ----------------------------------------------------------------
    audit = result.audit_record
    print(f"\n[6] Audit record:")
    print(f"    audit_id         : {audit.audit_id}")
    print(f"    outcome          : {audit.outcome_summary.value}")
    print(f"    action_taken     : {audit.action_taken.value}")

    print("\n" + "=" * 60)
    print("  Demo complete.")
    print()
    print("  The SIP broker produced a deterministic ExecutionPlan.")
    print("  A RAG adapter would now execute the retrieval query:")
    print(f"    query = \"{plan.grounded_parameters.get('query')}\"")
    print()
    print("  SIP never made a real network call. The plan is the")
    print("  contract between the control plane and the execution")
    print("  system. SIP's job ends here.")
    print("=" * 60)


if __name__ == "__main__":
    main()
