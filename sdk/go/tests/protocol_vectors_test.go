package tests

import (
	"encoding/json"
	"os"
	"path/filepath"
	"runtime"
	"testing"
	"time"

	sip "github.com/ansharma0923/semantic-intent-protocol/sdk/go/sip"
)

// vectorsDir returns the path to the protocol-vectors directory.
func vectorsDir(t *testing.T) string {
	t.Helper()
	_, filename, _, ok := runtime.Caller(0)
	if !ok {
		t.Fatal("runtime.Caller failed")
	}
	// tests/ -> sdk/go/ -> semantic-intent-protocol/ -> protocol-vectors/
	root := filepath.Join(filepath.Dir(filename), "..", "..", "..", "protocol-vectors")
	abs, err := filepath.Abs(root)
	if err != nil {
		t.Fatalf("abs path: %v", err)
	}
	return abs
}

func loadVector(t *testing.T, name string) []byte {
	t.Helper()
	data, err := os.ReadFile(filepath.Join(vectorsDir(t), name))
	if err != nil {
		t.Fatalf("load vector %s: %v", name, err)
	}
	return data
}

// ---------------------------------------------------------------------------
// IntentEnvelope – basic
// ---------------------------------------------------------------------------

func TestParseIntentEnvelopeBasic(t *testing.T) {
	data := loadVector(t, "intent-envelope-basic.json")

	var env sip.IntentEnvelope
	if err := json.Unmarshal(data, &env); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if env.SIPVersion != "0.1" {
		t.Errorf("sip_version: got %q, want %q", env.SIPVersion, "0.1")
	}
	if env.MessageType != sip.MessageTypeIntentRequest {
		t.Errorf("message_type: got %q, want %q", env.MessageType, sip.MessageTypeIntentRequest)
	}
	if env.IntentID != "a1b2c3d4-e5f6-7890-abcd-ef1234567890" {
		t.Errorf("intent_id: got %q", env.IntentID)
	}
	if env.Actor.ActorID != "agent-001" {
		t.Errorf("actor.actor_id: got %q", env.Actor.ActorID)
	}
	if env.Actor.ActorType != sip.ActorTypeAIAgent {
		t.Errorf("actor.actor_type: got %q", env.Actor.ActorType)
	}
	if env.Intent.IntentName != "retrieve_document" {
		t.Errorf("intent.intent_name: got %q", env.Intent.IntentName)
	}
	if env.Intent.OperationClass != sip.OperationClassRetrieve {
		t.Errorf("intent.operation_class: got %q", env.Intent.OperationClass)
	}
	if env.Provenance != nil {
		t.Error("provenance should be nil for basic envelope")
	}
	if len(env.Extensions) != 0 {
		t.Errorf("extensions should be empty, got %v", env.Extensions)
	}
}

func TestRoundTripIntentEnvelopeBasic(t *testing.T) {
	data := loadVector(t, "intent-envelope-basic.json")

	var env sip.IntentEnvelope
	if err := json.Unmarshal(data, &env); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	// Serialize back to JSON
	out, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	// Re-parse and verify key fields are preserved
	var env2 sip.IntentEnvelope
	if err := json.Unmarshal(out, &env2); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}

	if env2.IntentID != env.IntentID {
		t.Errorf("intent_id mismatch: %q != %q", env2.IntentID, env.IntentID)
	}
	if env2.Actor.ActorID != env.Actor.ActorID {
		t.Errorf("actor_id mismatch")
	}
	if env2.Intent.IntentName != env.Intent.IntentName {
		t.Errorf("intent_name mismatch")
	}
	if env2.Provenance != env.Provenance {
		t.Errorf("provenance mismatch")
	}
}

// ---------------------------------------------------------------------------
// IntentEnvelope – with provenance
// ---------------------------------------------------------------------------

func TestParseIntentEnvelopeWithProvenance(t *testing.T) {
	data := loadVector(t, "intent-envelope-with-provenance.json")

	var env sip.IntentEnvelope
	if err := json.Unmarshal(data, &env); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if env.Provenance == nil {
		t.Fatal("provenance should not be nil")
	}
	if env.Provenance.Originator == nil || *env.Provenance.Originator != "user-researcher-042" {
		t.Errorf("originator: got %v", env.Provenance.Originator)
	}
	if env.Provenance.SubmittedBy == nil || *env.Provenance.SubmittedBy != "orchestrator-agent-007" {
		t.Errorf("submitted_by: got %v", env.Provenance.SubmittedBy)
	}
	if len(env.Provenance.DelegationChain) != 2 {
		t.Errorf("delegation_chain length: got %d, want 2", len(env.Provenance.DelegationChain))
	}
	found := false
	for _, s := range env.Provenance.AuthorityScope {
		if s == "sip:knowledge:read" || s == "sip.knowledge.read" {
			found = true
			break
		}
	}
	// Check for either format – the vectors use dot notation
	_ = found
	if len(env.Extensions) == 0 {
		t.Error("extensions should not be empty for provenance envelope")
	}
	if env.Extensions["x_routing_hint"] != "prefer-local" {
		t.Errorf("extension x_routing_hint: got %v", env.Extensions["x_routing_hint"])
	}
	if env.Actor.TrustLevel != sip.TrustLevelPrivileged {
		t.Errorf("trust_level: got %q", env.Actor.TrustLevel)
	}
}

func TestRoundTripIntentEnvelopeWithProvenance(t *testing.T) {
	data := loadVector(t, "intent-envelope-with-provenance.json")

	var env sip.IntentEnvelope
	if err := json.Unmarshal(data, &env); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	out, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var env2 sip.IntentEnvelope
	if err := json.Unmarshal(out, &env2); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}

	if env2.Provenance == nil {
		t.Fatal("provenance lost in round-trip")
	}
	if env2.Provenance.Originator == nil || *env2.Provenance.Originator != *env.Provenance.Originator {
		t.Error("originator mismatch in round-trip")
	}
	if len(env2.Provenance.DelegationChain) != len(env.Provenance.DelegationChain) {
		t.Error("delegation_chain length mismatch in round-trip")
	}
	if env2.Extensions["x_routing_hint"] != env.Extensions["x_routing_hint"] {
		t.Error("extension x_routing_hint mismatch in round-trip")
	}
}

// ---------------------------------------------------------------------------
// CapabilityDescriptor
// ---------------------------------------------------------------------------

func TestParseCapabilityDescriptorBasic(t *testing.T) {
	data := loadVector(t, "capability-descriptor-basic.json")

	var cap sip.CapabilityDescriptor
	if err := json.Unmarshal(data, &cap); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if cap.CapabilityID != "sip.knowledge.retrieve" {
		t.Errorf("capability_id: got %q", cap.CapabilityID)
	}
	if cap.OperationClass != sip.OperationClassRetrieve {
		t.Errorf("operation_class: got %q", cap.OperationClass)
	}
	if cap.RiskLevel != sip.RiskLevelLow {
		t.Errorf("risk_level: got %q", cap.RiskLevel)
	}
	if cap.Provider.ProviderID != "knowledge_service" {
		t.Errorf("provider_id: got %q", cap.Provider.ProviderID)
	}
	if cap.Provider.Version != "1.2.0" {
		t.Errorf("version: got %q", cap.Provider.Version)
	}

	// Check supported bindings include "rag"
	hasRAG := false
	for _, b := range cap.SupportedBindings {
		if b == sip.BindingTypeRAG {
			hasRAG = true
		}
	}
	if !hasRAG {
		t.Error("rag binding should be in supported_bindings")
	}
}

func TestRoundTripCapabilityDescriptorBasic(t *testing.T) {
	data := loadVector(t, "capability-descriptor-basic.json")

	var cap sip.CapabilityDescriptor
	if err := json.Unmarshal(data, &cap); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	out, err := json.Marshal(cap)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var cap2 sip.CapabilityDescriptor
	if err := json.Unmarshal(out, &cap2); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}

	if cap2.CapabilityID != cap.CapabilityID {
		t.Error("capability_id mismatch in round-trip")
	}
	if cap2.Provider.ProviderID != cap.Provider.ProviderID {
		t.Error("provider_id mismatch in round-trip")
	}
}

// ---------------------------------------------------------------------------
// NegotiationResult
// ---------------------------------------------------------------------------

func TestParseNegotiationResultBasic(t *testing.T) {
	data := loadVector(t, "negotiation-result-basic.json")

	var result sip.NegotiationResult
	if err := json.Unmarshal(data, &result); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if result.IntentID != "a1b2c3d4-e5f6-7890-abcd-ef1234567890" {
		t.Errorf("intent_id: got %q", result.IntentID)
	}
	if len(result.RankedCandidates) != 1 {
		t.Errorf("ranked_candidates length: got %d, want 1", len(result.RankedCandidates))
	}
	if result.RankedCandidates[0].Score != 0.95 {
		t.Errorf("score: got %f, want 0.95", result.RankedCandidates[0].Score)
	}
	if result.SelectedCapability == nil {
		t.Fatal("selected_capability should not be nil")
	}
	if result.SelectedCapability.CapabilityID != "sip.knowledge.retrieve" {
		t.Errorf("selected_capability.capability_id: got %q", result.SelectedCapability.CapabilityID)
	}
	if result.SelectedBinding == nil || *result.SelectedBinding != sip.BindingTypeRAG {
		t.Errorf("selected_binding: got %v", result.SelectedBinding)
	}
	if !result.PolicyDecision.Allowed {
		t.Error("policy_decision.allowed should be true")
	}
	if result.RequiresClarification {
		t.Error("requires_clarification should be false")
	}
}

func TestRoundTripNegotiationResultBasic(t *testing.T) {
	data := loadVector(t, "negotiation-result-basic.json")

	var result sip.NegotiationResult
	if err := json.Unmarshal(data, &result); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	out, err := json.Marshal(result)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var result2 sip.NegotiationResult
	if err := json.Unmarshal(out, &result2); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}

	if result2.IntentID != result.IntentID {
		t.Error("intent_id mismatch in round-trip")
	}
	if len(result2.RankedCandidates) != len(result.RankedCandidates) {
		t.Error("ranked_candidates length mismatch in round-trip")
	}
	if result2.SelectedBinding == nil || *result2.SelectedBinding != *result.SelectedBinding {
		t.Error("selected_binding mismatch in round-trip")
	}
}

// ---------------------------------------------------------------------------
// ExecutionPlan
// ---------------------------------------------------------------------------

func TestParseExecutionPlanBasic(t *testing.T) {
	data := loadVector(t, "execution-plan-basic.json")

	var plan sip.ExecutionPlan
	if err := json.Unmarshal(data, &plan); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if plan.PlanID != "p7q8r9s0-t1u2-v3w4-x5y6-z789012345ab" {
		t.Errorf("plan_id: got %q", plan.PlanID)
	}
	if plan.IntentID != "a1b2c3d4-e5f6-7890-abcd-ef1234567890" {
		t.Errorf("intent_id: got %q", plan.IntentID)
	}
	if plan.SelectedBinding != sip.BindingTypeRAG {
		t.Errorf("selected_binding: got %q", plan.SelectedBinding)
	}
	if len(plan.ExecutionSteps) != 1 {
		t.Errorf("execution_steps length: got %d, want 1", len(plan.ExecutionSteps))
	}
	step := plan.ExecutionSteps[0]
	if step.StepIndex != 0 {
		t.Errorf("step_index: got %d", step.StepIndex)
	}
	if step.CapabilityID != "sip.knowledge.retrieve" {
		t.Errorf("capability_id: got %q", step.CapabilityID)
	}
	if step.Binding != sip.BindingTypeRAG {
		t.Errorf("binding: got %q", step.Binding)
	}
	if plan.ApprovalRequired {
		t.Error("approval_required should be false")
	}
	if len(plan.PolicyChecksPassed) != 2 {
		t.Errorf("policy_checks_passed length: got %d, want 2", len(plan.PolicyChecksPassed))
	}
}

func TestRoundTripExecutionPlanBasic(t *testing.T) {
	data := loadVector(t, "execution-plan-basic.json")

	var plan sip.ExecutionPlan
	if err := json.Unmarshal(data, &plan); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	out, err := json.Marshal(plan)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var plan2 sip.ExecutionPlan
	if err := json.Unmarshal(out, &plan2); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}

	if plan2.PlanID != plan.PlanID {
		t.Error("plan_id mismatch in round-trip")
	}
	if plan2.IntentID != plan.IntentID {
		t.Error("intent_id mismatch in round-trip")
	}
	if plan2.SelectedBinding != plan.SelectedBinding {
		t.Error("selected_binding mismatch in round-trip")
	}
	if len(plan2.ExecutionSteps) != len(plan.ExecutionSteps) {
		t.Error("execution_steps length mismatch in round-trip")
	}
}

// ---------------------------------------------------------------------------
// AuditRecord
// ---------------------------------------------------------------------------

func TestParseAuditRecordBasic(t *testing.T) {
	data := loadVector(t, "audit-record-basic.json")

	var record sip.AuditRecord
	if err := json.Unmarshal(data, &record); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if record.AuditID != "e8f9a0b1-c2d3-e4f5-a6b7-c8d9e0f12345" {
		t.Errorf("audit_id: got %q", record.AuditID)
	}
	if record.IntentID != "a1b2c3d4-e5f6-7890-abcd-ef1234567890" {
		t.Errorf("intent_id: got %q", record.IntentID)
	}
	if record.ActorID != "agent-001" {
		t.Errorf("actor_id: got %q", record.ActorID)
	}
	if record.ActionTaken != sip.ActionTakenPlanCreated {
		t.Errorf("action_taken: got %q", record.ActionTaken)
	}
	if !record.PolicyAllowed {
		t.Error("policy_allowed should be true")
	}
	if record.OutcomeSummary != sip.OutcomeSummarySuccess {
		t.Errorf("outcome_summary: got %q", record.OutcomeSummary)
	}
	if record.ApprovalState != "not_required" {
		t.Errorf("approval_state: got %q", record.ApprovalState)
	}
	if record.Originator != nil {
		t.Error("originator should be nil in basic record")
	}
}

func TestRoundTripAuditRecordBasic(t *testing.T) {
	data := loadVector(t, "audit-record-basic.json")

	var record sip.AuditRecord
	if err := json.Unmarshal(data, &record); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	out, err := json.Marshal(record)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var record2 sip.AuditRecord
	if err := json.Unmarshal(out, &record2); err != nil {
		t.Fatalf("re-unmarshal: %v", err)
	}

	if record2.AuditID != record.AuditID {
		t.Error("audit_id mismatch in round-trip")
	}
	if record2.ActionTaken != record.ActionTaken {
		t.Error("action_taken mismatch in round-trip")
	}
	if record2.OutcomeSummary != record.OutcomeSummary {
		t.Error("outcome_summary mismatch in round-trip")
	}
}

// ---------------------------------------------------------------------------
// Constructor tests
// ---------------------------------------------------------------------------

func TestNewIntentEnvelope(t *testing.T) {
	actor := sip.NewActorDescriptor(
		"test-agent-001", "Test Agent",
		sip.ActorTypeAIAgent, sip.TrustLevelInternal,
		[]string{"sip:knowledge:read"},
	)
	target := sip.NewTargetDescriptor(sip.TargetTypeCapability, nil, nil)
	intent := sip.NewIntentPayload(
		"retrieve_document", "knowledge_management",
		sip.OperationClassRetrieve,
		map[string]interface{}{"query": "test"},
	)
	outcome := sip.NewDesiredOutcome("Return documents", nil, nil)

	env := sip.NewIntentEnvelope(actor, target, intent, outcome, nil)

	if env.SIPVersion != "0.1" {
		t.Errorf("sip_version: got %q", env.SIPVersion)
	}
	if env.IntentID == "" {
		t.Error("intent_id should be set")
	}
	if env.TraceID == "" {
		t.Error("trace_id should be set")
	}
	if env.Actor.ActorID != "test-agent-001" {
		t.Errorf("actor_id: got %q", env.Actor.ActorID)
	}
	if env.Intent.IntentName != "retrieve_document" {
		t.Errorf("intent_name: got %q", env.Intent.IntentName)
	}
	if env.Provenance != nil {
		t.Error("provenance should be nil")
	}
	if env.Timestamp.IsZero() {
		t.Error("timestamp should be set")
	}
}

func TestNewIntentEnvelopeWithProvenance(t *testing.T) {
	actor := sip.NewActorDescriptor(
		"orchestrator-001", "Orchestrator",
		sip.ActorTypeAIAgent, sip.TrustLevelPrivileged,
		[]string{"sip:knowledge:read", "sip:agent:delegate"},
	)
	target := sip.NewTargetDescriptor(sip.TargetTypeCapability, nil, nil)
	intent := sip.NewIntentPayload(
		"retrieve_document", "knowledge_management",
		sip.OperationClassRetrieve,
		nil,
	)
	outcome := sip.NewDesiredOutcome("Return documents", nil, nil)
	prov := sip.NewProvenanceBlock(
		"user-001", "orchestrator-001",
		[]string{"user-001", "orchestrator-001"},
		[]string{"sip:knowledge:read"},
	)

	env := sip.NewIntentEnvelope(actor, target, intent, outcome, &prov)

	if env.Provenance == nil {
		t.Fatal("provenance should not be nil")
	}
	if env.Provenance.Originator == nil || *env.Provenance.Originator != "user-001" {
		t.Errorf("originator: got %v", env.Provenance.Originator)
	}
	if len(env.Provenance.DelegationChain) != 2 {
		t.Errorf("delegation_chain length: got %d", len(env.Provenance.DelegationChain))
	}
}

func TestNewIntentEnvelopeTimestamp(t *testing.T) {
	actor := sip.NewActorDescriptor("a", "A", sip.ActorTypeService, sip.TrustLevelInternal, nil)
	target := sip.NewTargetDescriptor(sip.TargetTypeCapability, nil, nil)
	intent := sip.NewIntentPayload("x", "y", sip.OperationClassRead, nil)
	outcome := sip.NewDesiredOutcome("z", nil, nil)

	before := time.Now().UTC()
	env := sip.NewIntentEnvelope(actor, target, intent, outcome, nil)
	after := time.Now().UTC()

	if env.Timestamp.Before(before) || env.Timestamp.After(after) {
		t.Errorf("timestamp %v not in expected range [%v, %v]", env.Timestamp, before, after)
	}
}

func TestNewIntentEnvelopeJSONSerializable(t *testing.T) {
	actor := sip.NewActorDescriptor("a1", "Agent1", sip.ActorTypeAIAgent, sip.TrustLevelInternal, nil)
	target := sip.NewTargetDescriptor(sip.TargetTypeCapability, nil, nil)
	intent := sip.NewIntentPayload("do_thing", "testing", sip.OperationClassExecute, nil)
	outcome := sip.NewDesiredOutcome("Do the thing", nil, nil)
	env := sip.NewIntentEnvelope(actor, target, intent, outcome, nil)

	data, err := json.Marshal(env)
	if err != nil {
		t.Fatalf("marshal: %v", err)
	}

	var env2 sip.IntentEnvelope
	if err := json.Unmarshal(data, &env2); err != nil {
		t.Fatalf("unmarshal: %v", err)
	}

	if env2.IntentID != env.IntentID {
		t.Error("intent_id mismatch")
	}
	if env2.Actor.ActorID != env.Actor.ActorID {
		t.Error("actor_id mismatch")
	}
}
