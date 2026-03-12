// Command basic_usage demonstrates how to use the SIP Go SDK.
//
// This example shows how to:
//   - Construct an IntentEnvelope using helper constructors
//   - Serialize it to JSON for inspection
//   - Send it to a SIP broker using BrokerClient
//   - Handle the response
//
// To run against a live broker:
//
//	go run basic_usage.go -broker http://localhost:8000
//
// To run without a live broker (dry-run mode, shows envelope only):
//
//	go run basic_usage.go -dry-run
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

	// -----------------------------------------------------------------------
	// Step 1: Construct the actor
	// -----------------------------------------------------------------------
	actor := sip.NewActorDescriptor(
		"example-go-agent-001",
		"Go SDK Example Agent",
		sip.ActorTypeAIAgent,
		sip.TrustLevelInternal,
		[]string{"sip:knowledge:read"},
	)

	// -----------------------------------------------------------------------
	// Step 2: Construct the target
	// -----------------------------------------------------------------------
	target := sip.NewTargetDescriptor(
		sip.TargetTypeCapability,
		nil,  // no specific target_id; let the broker select the best capability
		strPtr("knowledge_management"),
	)

	// -----------------------------------------------------------------------
	// Step 3: Construct the intent payload
	// -----------------------------------------------------------------------
	intent := sip.NewIntentPayload(
		"retrieve_document",       // intent_name
		"knowledge_management",   // intent_domain
		sip.OperationClassRetrieve,
		map[string]interface{}{
			"query": "SIP protocol architecture overview",
			"top_k": 5,
			"format": "json",
		},
	)

	// -----------------------------------------------------------------------
	// Step 4: Specify the desired outcome
	// -----------------------------------------------------------------------
	outputFormat := "json"
	outcome := sip.NewDesiredOutcome(
		"Return top-5 documents relevant to SIP protocol architecture",
		&outputFormat,
		[]string{
			"At least one document returned",
			"Documents ranked by relevance score",
		},
	)

	// -----------------------------------------------------------------------
	// Step 5: Assemble the IntentEnvelope (no provenance for this basic example)
	// -----------------------------------------------------------------------
	envelope := sip.NewIntentEnvelope(actor, target, intent, outcome, nil)

	// Add a preferred RAG binding
	envelope.ProtocolBindings = []sip.ProtocolBinding{
		{
			BindingType: sip.BindingTypeRAG,
			Metadata:    map[string]interface{}{},
		},
	}

	// -----------------------------------------------------------------------
	// Step 6: Print the envelope JSON
	// -----------------------------------------------------------------------
	envJSON, err := json.MarshalIndent(envelope, "", "  ")
	if err != nil {
		log.Fatalf("serialize envelope: %v", err)
	}
	fmt.Println("=== IntentEnvelope ===")
	fmt.Println(string(envJSON))

	if *dryRun {
		fmt.Println("\n[dry-run] Not sending to broker.")
		os.Exit(0)
	}

	// -----------------------------------------------------------------------
	// Step 7: Send the envelope to the SIP broker
	// -----------------------------------------------------------------------
	fmt.Printf("\n=== Submitting to broker: %s ===\n", *brokerURL)
	client := sip.NewBrokerClient(*brokerURL)
	ctx := context.Background()

	// Optional: check broker health first
	health, err := client.Health(ctx)
	if err != nil {
		fmt.Printf("Warning: health check failed: %v\n", err)
	} else {
		fmt.Printf("Broker status: %s (capabilities: %d)\n", health.Status, health.Capabilities)
	}

	// Submit the intent
	response, statusCode, err := client.SubmitIntent(ctx, envelope)
	if err != nil {
		log.Fatalf("submit intent: %v", err)
	}

	// -----------------------------------------------------------------------
	// Step 8: Handle the response
	// -----------------------------------------------------------------------
	fmt.Printf("\n=== Response (HTTP %d) ===\n", statusCode)
	respJSON, _ := json.MarshalIndent(response, "", "  ")
	fmt.Println(string(respJSON))

	fmt.Printf("\nOutcome: %s\n", response.Outcome)
	fmt.Printf("Action taken: %s\n", response.ActionTaken)
	fmt.Printf("Policy allowed: %v\n", response.PolicyAllowed)
	if response.ApprovalRequired {
		fmt.Println("Note: Human approval is required before execution.")
	}
}

// strPtr returns a pointer to the given string.
func strPtr(s string) *string {
	return &s
}
