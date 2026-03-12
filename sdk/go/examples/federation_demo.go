// Command federation_demo demonstrates broker federation using the SIP Go SDK.
//
// This example shows how to:
//   - Construct an IntentEnvelope for a cross-broker scenario
//   - Print the envelope JSON for inspection
//   - Optionally submit it to a running SIP broker
//   - Interpret the response including federation metadata
//
// Dry-run mode (no broker required):
//
//	go run federation_demo.go -dry-run
//
// Submit to a running broker:
//
//	go run federation_demo.go -broker http://localhost:8000
//
// The broker must be running with federation configured for Broker B.
// See examples/end_to_end_demo/demo_overview.md for setup instructions.
package main

import (
	"context"
	"encoding/json"
	"flag"
	"fmt"
	"log"
	"os"

	sip "github.com/ansharma0923/semantic-intent-protocol/sdk/go/sip"
)

func main() {
	brokerURL := flag.String("broker", "http://localhost:8000", "SIP broker base URL")
	dryRun := flag.Bool("dry-run", false, "Print envelope JSON and exit without sending")
	flag.Parse()

	fmt.Println("=== SIP Go SDK – Federation Demo ===\n")

	// -----------------------------------------------------------------------
	// Step 1: Construct the actor (federation-aware AI agent)
	// -----------------------------------------------------------------------
	fmt.Println("Step 1: Building actor...")
	actor := sip.NewActorDescriptor(
		"go-federation-agent-001",
		"Go Federation Agent",
		sip.ActorTypeAIAgent,
		sip.TrustLevelInternal,
		[]string{"sip:knowledge:read", "sip:analytics:read"},
	)
	fmt.Printf("  actor_id:    %s\n", actor.ActorID)
	fmt.Printf("  actor_type:  %s\n", actor.ActorType)
	fmt.Printf("  trust_level: %s\n", actor.TrustLevel)
	fmt.Printf("  scopes:      %v\n", actor.Scopes)

	// -----------------------------------------------------------------------
	// Step 2: Construct the target (let the broker select across federation)
	// -----------------------------------------------------------------------
	fmt.Println("\nStep 2: Building target...")
	target := sip.NewTargetDescriptor(
		sip.TargetTypeCapability,
		nil, // no specific target_id — broker selects best match (may federate)
		strPtr("knowledge_management"),
	)
	fmt.Printf("  target_type:  %s\n", target.TargetType)
	fmt.Printf("  namespace:    %s\n", ptrStr(target.Namespace))

	// -----------------------------------------------------------------------
	// Step 3: Construct the intent payload
	// -----------------------------------------------------------------------
	fmt.Println("\nStep 3: Building intent payload...")
	intent := sip.NewIntentPayload(
		"retrieve_document",      // intent_name
		"knowledge_management",   // intent_domain
		sip.OperationClassRetrieve,
		map[string]interface{}{
			"query":       "SIP protocol federation architecture",
			"top_k":       5,
			"format":      "json",
			"cross_broker": true, // hint: allow federated results
		},
	)
	fmt.Printf("  intent_name:   %s\n", intent.IntentName)
	fmt.Printf("  intent_domain: %s\n", intent.IntentDomain)
	fmt.Printf("  operation:     %s\n", intent.OperationClass)

	// -----------------------------------------------------------------------
	// Step 4: Specify the desired outcome
	// -----------------------------------------------------------------------
	fmt.Println("\nStep 4: Building desired outcome...")
	outputFormat := "json"
	outcome := sip.NewDesiredOutcome(
		"Return top-5 documents about SIP federation architecture, potentially from federated brokers",
		&outputFormat,
		[]string{
			"At least one document returned",
			"Federation metadata included if remote capabilities were used",
			"Provenance chain preserved",
		},
	)
	fmt.Printf("  summary: %s\n", outcome.Summary)

	// -----------------------------------------------------------------------
	// Step 5: Build provenance block (delegation chain)
	// -----------------------------------------------------------------------
	fmt.Println("\nStep 5: Building provenance block...")
	provenance := sip.NewProvenanceBlock(
		"user-bob",
		"go-federation-agent-001",
		[]string{"user-bob"},
		[]string{"sip:knowledge:read", "sip:analytics:read"},
	)
	fmt.Printf("  originator:       %s\n", ptrStr(provenance.Originator))
	fmt.Printf("  submitted_by:     %s\n", ptrStr(provenance.SubmittedBy))
	fmt.Printf("  delegation_chain: %v\n", provenance.DelegationChain)

	// -----------------------------------------------------------------------
	// Step 6: Assemble the IntentEnvelope
	// -----------------------------------------------------------------------
	fmt.Println("\nStep 6: Assembling IntentEnvelope...")
	envelope := sip.NewIntentEnvelope(actor, target, intent, outcome, &provenance)

	// Add preferred bindings (RAG first, REST as fallback)
	envelope.ProtocolBindings = []sip.ProtocolBinding{
		{BindingType: sip.BindingTypeRAG, Metadata: map[string]interface{}{}},
		{BindingType: sip.BindingTypeREST, Metadata: map[string]interface{}{}},
	}
	fmt.Printf("  intent_id:   %s\n", envelope.IntentID)
	fmt.Printf("  trace_id:    %s\n", envelope.TraceID)
	fmt.Printf("  sip_version: %s\n", envelope.SIPVersion)

	// -----------------------------------------------------------------------
	// Step 7: Serialize and print the envelope
	// -----------------------------------------------------------------------
	fmt.Println("\nStep 7: Serializing IntentEnvelope to JSON...")
	envJSON, err := json.MarshalIndent(envelope, "", "  ")
	if err != nil {
		log.Fatalf("serialize envelope: %v", err)
	}
	fmt.Println("\n=== IntentEnvelope (JSON) ===")
	fmt.Println(string(envJSON))

	if *dryRun {
		fmt.Println("\n[dry-run] Not sending to broker.")
		fmt.Println("\n=== Demo complete (dry-run). ===")
		os.Exit(0)
	}

	// -----------------------------------------------------------------------
	// Step 8: Submit to the broker
	// -----------------------------------------------------------------------
	fmt.Printf("\n=== Submitting to broker: %s ===\n", *brokerURL)
	client := sip.NewBrokerClient(*brokerURL)
	ctx := context.Background()

	// Health check
	health, err := client.Health(ctx)
	if err != nil {
		fmt.Printf("Warning: health check failed: %v\n", err)
	} else {
		fmt.Printf("Broker status: %s  capabilities: %d  version: %s\n",
			health.Status, health.Capabilities, health.Version)
	}

	// Submit the intent
	response, statusCode, err := client.SubmitIntent(ctx, envelope)
	if err != nil {
		log.Fatalf("submit intent: %v", err)
	}

	// -----------------------------------------------------------------------
	// Step 9: Print the response
	// -----------------------------------------------------------------------
	fmt.Printf("\n=== Response (HTTP %d) ===\n", statusCode)
	respJSON, _ := json.MarshalIndent(response, "", "  ")
	fmt.Println(string(respJSON))

	fmt.Println("\n=== NegotiationResult summary ===")
	fmt.Printf("  intent_id:        %s\n", response.IntentID)
	fmt.Printf("  outcome:          %s\n", response.Outcome)
	fmt.Printf("  action_taken:     %s\n", response.ActionTaken)
	fmt.Printf("  policy_allowed:   %v\n", response.PolicyAllowed)
	fmt.Printf("  approval_required:%v\n", response.ApprovalRequired)
	if response.PlanID != nil {
		fmt.Printf("  plan_id:          %s\n", *response.PlanID)
	}

	fmt.Println("\n=== AuditRecord ===")
	auditJSON, _ := json.MarshalIndent(response.AuditRecord, "", "  ")
	fmt.Println(string(auditJSON))

	fmt.Println("\n=== Demo complete. ===")
}

// strPtr returns a pointer to a string value.
func strPtr(s string) *string {
	return &s
}

// ptrStr dereferences a string pointer safely.
func ptrStr(p *string) string {
	if p == nil {
		return "<nil>"
	}
	return *p
}
