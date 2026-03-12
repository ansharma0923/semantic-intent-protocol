package sip

import (
	"time"

	"github.com/google/uuid"
)

// ---------------------------------------------------------------------------
// Helper constructors
// ---------------------------------------------------------------------------

// NewActorDescriptor creates an ActorDescriptor with sensible defaults.
//
//   actor := sip.NewActorDescriptor("agent-001", "My Agent",
//       sip.ActorTypeAIAgent, sip.TrustLevelInternal,
//       []string{"sip:knowledge:read"})
func NewActorDescriptor(actorID, name string, actorType ActorType, trustLevel TrustLevel, scopes []string) ActorDescriptor {
	if scopes == nil {
		scopes = []string{}
	}
	return ActorDescriptor{
		ActorID:    actorID,
		ActorType:  actorType,
		Name:       name,
		TrustLevel: trustLevel,
		Scopes:     scopes,
	}
}

// NewTargetDescriptor creates a TargetDescriptor with the given target type.
//
//   target := sip.NewTargetDescriptor(sip.TargetTypeCapability, nil, nil)
func NewTargetDescriptor(targetType TargetType, targetID *string, namespace *string) TargetDescriptor {
	return TargetDescriptor{
		TargetType: targetType,
		TargetID:   targetID,
		Namespace:  namespace,
	}
}

// NewIntentPayload creates an IntentPayload with the given fields.
//
//   intent := sip.NewIntentPayload("retrieve_document", "knowledge_management",
//       sip.OperationClassRetrieve, map[string]interface{}{"query": "test"})
func NewIntentPayload(intentName, intentDomain string, operationClass OperationClass, parameters map[string]interface{}) IntentPayload {
	if parameters == nil {
		parameters = map[string]interface{}{}
	}
	return IntentPayload{
		IntentName:     intentName,
		IntentDomain:   intentDomain,
		OperationClass: operationClass,
		Parameters:     parameters,
	}
}

// NewDesiredOutcome creates a DesiredOutcome.
//
//   outcome := sip.NewDesiredOutcome("Return top-5 documents", nil, nil)
func NewDesiredOutcome(summary string, outputFormat *string, successCriteria []string) DesiredOutcome {
	if successCriteria == nil {
		successCriteria = []string{}
	}
	return DesiredOutcome{
		Summary:         summary,
		OutputFormat:    outputFormat,
		SuccessCriteria: successCriteria,
	}
}

// NewProvenanceBlock creates a ProvenanceBlock with the required fields.
//
//   prov := sip.NewProvenanceBlock("originator-001", "submitter-002",
//       []string{"originator-001", "submitter-002"},
//       []string{"sip:knowledge:read"})
func NewProvenanceBlock(originator, submittedBy string, delegationChain []string, authorityScope []string) ProvenanceBlock {
	if delegationChain == nil {
		delegationChain = []string{}
	}
	return ProvenanceBlock{
		Originator:      &originator,
		SubmittedBy:     &submittedBy,
		DelegationChain: delegationChain,
		AuthorityScope:  authorityScope,
	}
}

// NewIntentEnvelope creates a complete IntentEnvelope with all required fields
// and sensible defaults for optional fields.
//
//   actor := sip.NewActorDescriptor(...)
//   target := sip.NewTargetDescriptor(...)
//   intent := sip.NewIntentPayload(...)
//   outcome := sip.NewDesiredOutcome(...)
//
//   envelope := sip.NewIntentEnvelope(actor, target, intent, outcome, nil)
func NewIntentEnvelope(
	actor ActorDescriptor,
	target TargetDescriptor,
	intent IntentPayload,
	desiredOutcome DesiredOutcome,
	provenance *ProvenanceBlock,
) IntentEnvelope {
	now := time.Now().UTC()
	return IntentEnvelope{
		SIPVersion:  "0.1",
		MessageType: MessageTypeIntentRequest,
		IntentID:    uuid.New().String(),
		TraceID:     uuid.New().String(),
		SpanID:      uuid.New().String(),
		Timestamp:   now,
		Actor:       actor,
		Target:      target,
		Intent:      intent,
		DesiredOutcome: desiredOutcome,
		Constraints: Constraints{
			AllowedActions:      []string{},
			ForbiddenActions:    []string{},
			DataSensitivity:     DataSensitivityInternal,
			DeterminismRequired: DeterminismLevelStrict,
			Priority:            PriorityNormal,
		},
		Context: ContextBlock{
			Environment: "production",
			Additional:  map[string]interface{}{},
		},
		CapabilityRequirements: []CapabilityRequirement{},
		Trust: TrustBlock{
			DeclaredTrustLevel: actor.TrustLevel,
			DelegationChain:    []string{},
		},
		ProtocolBindings: []ProtocolBinding{},
		Negotiation: NegotiationHints{
			CandidateCapabilities: []string{},
			AllowFallback:         true,
			MaxCandidates:         5,
		},
		Integrity: IntegrityBlock{
			SchemaVersion: "0.1",
			Signed:        false,
		},
		Provenance: provenance,
		Extensions: map[string]interface{}{},
	}
}
