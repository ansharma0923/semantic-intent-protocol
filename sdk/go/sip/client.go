package sip

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net/http"
	"strings"
	"time"
)

// ---------------------------------------------------------------------------
// BrokerClient
// ---------------------------------------------------------------------------

// BrokerClient is an HTTP client for submitting intents to a SIP broker.
//
//   client := sip.NewBrokerClient("http://localhost:8000")
//   result, err := client.SubmitIntent(context.Background(), envelope)
type BrokerClient struct {
	baseURL    string
	httpClient *http.Client
}

// NewBrokerClient creates a new BrokerClient for the given broker base URL.
//
//   client := sip.NewBrokerClient("http://localhost:8000")
func NewBrokerClient(baseURL string) *BrokerClient {
	return &BrokerClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// HealthResponse is the response body of GET /healthz.
type HealthResponse struct {
	Status       string `json:"status"`
	Version      string `json:"version"`
	Capabilities int    `json:"capabilities"`
}

// IntentResponse is the response body of POST /sip/intents.
type IntentResponse struct {
	IntentID              string      `json:"intent_id"`
	Outcome               string      `json:"outcome"`
	ActionTaken           string      `json:"action_taken"`
	PolicyAllowed         bool        `json:"policy_allowed"`
	ApprovalRequired      bool        `json:"approval_required"`
	PlanID                *string     `json:"plan_id"`
	RequiresClarification bool        `json:"requires_clarification"`
	PolicyNotes           []string    `json:"policy_notes"`
	AuditRecord           AuditRecord `json:"audit_record"`
}

// Health calls GET /healthz and returns the health status.
func (c *BrokerClient) Health(ctx context.Context) (*HealthResponse, error) {
	url := c.baseURL + "/healthz"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build request GET %s: %w", url, err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("GET %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("health check failed (HTTP %d): %s", resp.StatusCode, string(body))
	}

	var health HealthResponse
	if err := json.NewDecoder(resp.Body).Decode(&health); err != nil {
		return nil, fmt.Errorf("decode health response: %w", err)
	}
	return &health, nil
}

// SubmitIntent sends an IntentEnvelope to POST /sip/intents and returns the
// broker response.
func (c *BrokerClient) SubmitIntent(ctx context.Context, envelope IntentEnvelope) (*IntentResponse, int, error) {
	data, err := json.Marshal(envelope)
	if err != nil {
		return nil, 0, fmt.Errorf("marshal envelope: %w", err)
	}
	return c.submitIntentBytes(ctx, data)
}

// SubmitIntentJSON sends a raw JSON string to POST /sip/intents.
func (c *BrokerClient) SubmitIntentJSON(ctx context.Context, jsonStr string) (*IntentResponse, int, error) {
	return c.submitIntentBytes(ctx, []byte(jsonStr))
}

func (c *BrokerClient) submitIntentBytes(ctx context.Context, data []byte) (*IntentResponse, int, error) {
	url := c.baseURL + "/sip/intents"
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return nil, 0, fmt.Errorf("build request POST %s: %w", url, err)
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, 0, fmt.Errorf("POST %s: %w", url, err)
	}
	defer resp.Body.Close()

	body, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, resp.StatusCode, fmt.Errorf("read response body: %w", err)
	}

	var intentResp IntentResponse
	if err := json.Unmarshal(body, &intentResp); err != nil {
		return nil, resp.StatusCode, fmt.Errorf("decode intent response (HTTP %d): %w", resp.StatusCode, err)
	}
	return &intentResp, resp.StatusCode, nil
}

// ---------------------------------------------------------------------------
// CapabilityDiscoveryClient
// ---------------------------------------------------------------------------

// CapabilityDiscoveryClient is an HTTP client for SIP capability discovery.
//
//   dc := sip.NewCapabilityDiscoveryClient("http://localhost:8000")
//   caps, err := dc.ListCapabilities(context.Background())
type CapabilityDiscoveryClient struct {
	baseURL    string
	httpClient *http.Client
}

// NewCapabilityDiscoveryClient creates a new CapabilityDiscoveryClient.
func NewCapabilityDiscoveryClient(baseURL string) *CapabilityDiscoveryClient {
	return &CapabilityDiscoveryClient{
		baseURL: strings.TrimRight(baseURL, "/"),
		httpClient: &http.Client{
			Timeout: 30 * time.Second,
		},
	}
}

// DiscoveryCandidate represents a single capability candidate in a discovery response.
type DiscoveryCandidate struct {
	CapabilityID   string  `json:"capability_id"`
	Score          float64 `json:"score"`
	Rationale      string  `json:"rationale"`
	SourceBrokerID *string `json:"source_broker_id"`
	RoutingAllowed bool    `json:"routing_allowed"`
}

// DiscoveryResponse is the response body of POST /sip/capabilities/discover.
type DiscoveryResponse struct {
	Total        int                  `json:"total"`
	LocalCount   int                  `json:"local_count"`
	RemoteCount  int                  `json:"remote_count"`
	Candidates   []DiscoveryCandidate `json:"candidates"`
	PeersQueried []string             `json:"peers_queried"`
	PeersFailed  []string             `json:"peers_failed"`
	Timestamp    string               `json:"timestamp"`
}

// DiscoveryRequest is the request body for POST /sip/capabilities/discover.
type DiscoveryRequest struct {
	IntentName            *string  `json:"intent_name,omitempty"`
	IntentDomain          *string  `json:"intent_domain,omitempty"`
	OperationClass        *string  `json:"operation_class,omitempty"`
	PreferredBindings     []string `json:"preferred_bindings,omitempty"`
	CandidateCapabilities []string `json:"candidate_capabilities,omitempty"`
	TrustLevel            *string  `json:"trust_level,omitempty"`
	MaxResults            int      `json:"max_results,omitempty"`
	IncludeRemote         bool     `json:"include_remote,omitempty"`
}

// ListCapabilities calls GET /sip/capabilities and returns all capability descriptors.
func (c *CapabilityDiscoveryClient) ListCapabilities(ctx context.Context) ([]CapabilityDescriptor, error) {
	url := c.baseURL + "/sip/capabilities"
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build request GET %s: %w", url, err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("GET %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("list capabilities failed (HTTP %d): %s", resp.StatusCode, string(body))
	}

	var caps []CapabilityDescriptor
	if err := json.NewDecoder(resp.Body).Decode(&caps); err != nil {
		return nil, fmt.Errorf("decode capabilities: %w", err)
	}
	return caps, nil
}

// GetCapability calls GET /sip/capabilities/{id} and returns the capability descriptor.
func (c *CapabilityDiscoveryClient) GetCapability(ctx context.Context, capabilityID string) (*CapabilityDescriptor, error) {
	url := c.baseURL + "/sip/capabilities/" + capabilityID
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, fmt.Errorf("build request GET %s: %w", url, err)
	}
	resp, err := c.httpClient.Do(req)
	if err != nil {
		return nil, fmt.Errorf("GET %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode == http.StatusNotFound {
		return nil, fmt.Errorf("capability not found: %s", capabilityID)
	}
	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("get capability failed (HTTP %d): %s", resp.StatusCode, string(body))
	}

	var cap CapabilityDescriptor
	if err := json.NewDecoder(resp.Body).Decode(&cap); err != nil {
		return nil, fmt.Errorf("decode capability: %w", err)
	}
	return &cap, nil
}

// DiscoverCapabilities calls POST /sip/capabilities/discover and returns ranked candidates.
func (c *CapabilityDiscoveryClient) DiscoverCapabilities(ctx context.Context, req DiscoveryRequest) (*DiscoveryResponse, error) {
	data, err := json.Marshal(req)
	if err != nil {
		return nil, fmt.Errorf("marshal discovery request: %w", err)
	}

	url := c.baseURL + "/sip/capabilities/discover"
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, url, bytes.NewReader(data))
	if err != nil {
		return nil, fmt.Errorf("build request POST %s: %w", url, err)
	}
	httpReq.Header.Set("Content-Type", "application/json")

	resp, err := c.httpClient.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("POST %s: %w", url, err)
	}
	defer resp.Body.Close()

	if resp.StatusCode != http.StatusOK {
		body, _ := io.ReadAll(resp.Body)
		return nil, fmt.Errorf("discover capabilities failed (HTTP %d): %s", resp.StatusCode, string(body))
	}

	var discResp DiscoveryResponse
	if err := json.NewDecoder(resp.Body).Decode(&discResp); err != nil {
		return nil, fmt.Errorf("decode discovery response: %w", err)
	}
	return &discResp, nil
}

