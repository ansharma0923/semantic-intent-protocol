// Package sip provides Go representations of core Semantic Intent Protocol
// (SIP) objects, helper constructors, and HTTP client support for interacting
// with a SIP broker.
//
// JSON field names match the SIP protocol specification (v0.1) exactly so
// that values serialized by this SDK are compatible with the canonical
// protocol vectors in protocol-vectors/.
package sip

import (
	"time"
)

// ---------------------------------------------------------------------------
// Enumerations (string-typed for JSON compatibility)
// ---------------------------------------------------------------------------

// ActorType classifies the entity submitting an intent.
type ActorType string

const (
	ActorTypeHuman    ActorType = "human"
	ActorTypeAIAgent  ActorType = "ai_agent"
	ActorTypeService  ActorType = "service"
	ActorTypeSystem   ActorType = "system"
)

// TargetType classifies the intended target of an intent.
type TargetType string

const (
	TargetTypeCapability TargetType = "capability"
	TargetTypeAgent      TargetType = "agent"
	TargetTypeService    TargetType = "service"
	TargetTypeRegistry   TargetType = "registry"
	TargetTypeBroadcast  TargetType = "broadcast"
)

// OperationClass is the high-level classification of the requested operation.
type OperationClass string

const (
	OperationClassRead     OperationClass = "read"
	OperationClassWrite    OperationClass = "write"
	OperationClassExecute  OperationClass = "execute"
	OperationClassAnalyze  OperationClass = "analyze"
	OperationClassRetrieve OperationClass = "retrieve"
	OperationClassDelegate OperationClass = "delegate"
)

// Priority is the execution priority hint.
type Priority string

const (
	PriorityLow      Priority = "low"
	PriorityNormal   Priority = "normal"
	PriorityHigh     Priority = "high"
	PriorityCritical Priority = "critical"
)

// DeterminismLevel is the required determinism level for execution.
type DeterminismLevel string

const (
	DeterminismLevelStrict   DeterminismLevel = "strict"
	DeterminismLevelBounded  DeterminismLevel = "bounded"
	DeterminismLevelAdvisory DeterminismLevel = "advisory"
)

// TrustLevel is the trust tier of the originating actor.
type TrustLevel string

const (
	TrustLevelPublic     TrustLevel = "public"
	TrustLevelInternal   TrustLevel = "internal"
	TrustLevelPrivileged TrustLevel = "privileged"
	TrustLevelAdmin      TrustLevel = "admin"
)

// DataSensitivity is the data sensitivity classification.
type DataSensitivity string

const (
	DataSensitivityPublic       DataSensitivity = "public"
	DataSensitivityInternal     DataSensitivity = "internal"
	DataSensitivityConfidential DataSensitivity = "confidential"
	DataSensitivityRestricted   DataSensitivity = "restricted"
)

// BindingType identifies the execution protocol binding.
type BindingType string

const (
	BindingTypeREST BindingType = "rest"
	BindingTypeGRPC BindingType = "grpc"
	BindingTypeMCP  BindingType = "mcp"
	BindingTypeA2A  BindingType = "a2a"
	BindingTypeRAG  BindingType = "rag"
)

// MessageType classifies the SIP message.
type MessageType string

const (
	MessageTypeIntentRequest     MessageType = "intent_request"
	MessageTypeIntentResponse    MessageType = "intent_response"
	MessageTypeCapabilityQuery   MessageType = "capability_query"
	MessageTypeCapabilityResponse MessageType = "capability_response"
	MessageTypeNegotiationResult MessageType = "negotiation_result"
	MessageTypeExecutionPlan     MessageType = "execution_plan"
	MessageTypeAuditRecord       MessageType = "audit_record"
)

// RiskLevel is the risk level of invoking a capability.
type RiskLevel string

const (
	RiskLevelLow      RiskLevel = "low"
	RiskLevelMedium   RiskLevel = "medium"
	RiskLevelHigh     RiskLevel = "high"
	RiskLevelCritical RiskLevel = "critical"
)

// ActionTaken records what action was taken after policy evaluation.
type ActionTaken string

const (
	ActionTakenPlanCreated            ActionTaken = "plan_created"
	ActionTakenPlanRejected           ActionTaken = "plan_rejected"
	ActionTakenApprovalRequested      ActionTaken = "approval_requested"
	ActionTakenClarificationRequested ActionTaken = "clarification_requested"
	ActionTakenPolicyDenied           ActionTaken = "policy_denied"
	ActionTakenValidationFailed       ActionTaken = "validation_failed"
)

// OutcomeSummary is the high-level outcome of processing an intent.
type OutcomeSummary string

const (
	OutcomeSummarySuccess             OutcomeSummary = "success"
	OutcomeSummaryPendingApproval     OutcomeSummary = "pending_approval"
	OutcomeSummaryNeedsClarification  OutcomeSummary = "needs_clarification"
	OutcomeSummaryDenied              OutcomeSummary = "denied"
	OutcomeSummaryError               OutcomeSummary = "error"
)

// ---------------------------------------------------------------------------
// Nested models
// ---------------------------------------------------------------------------

// ActorDescriptor describes the entity originating the intent.
type ActorDescriptor struct {
	ActorID    string     `json:"actor_id"`
	ActorType  ActorType  `json:"actor_type"`
	Name       string     `json:"name"`
	TrustLevel TrustLevel `json:"trust_level"`
	Scopes     []string   `json:"scopes"`
}

// TargetDescriptor describes the intended target of an intent.
type TargetDescriptor struct {
	TargetType TargetType `json:"target_type"`
	TargetID   *string    `json:"target_id"`
	Namespace  *string    `json:"namespace"`
}

// IntentPayload is the semantic intent being expressed.
type IntentPayload struct {
	IntentName          string                 `json:"intent_name"`
	IntentDomain        string                 `json:"intent_domain"`
	OperationClass      OperationClass         `json:"operation_class"`
	NaturalLanguageHint *string                `json:"natural_language_hint"`
	Parameters          map[string]interface{} `json:"parameters"`
}

// DesiredOutcome describes what the actor wants as a result.
type DesiredOutcome struct {
	Summary         string   `json:"summary"`
	OutputFormat    *string  `json:"output_format"`
	SuccessCriteria []string `json:"success_criteria"`
}

// Constraints defines execution constraints on the intent.
type Constraints struct {
	TimeBudgetMs         *int             `json:"time_budget_ms"`
	CostBudget           *float64         `json:"cost_budget"`
	AllowedActions       []string         `json:"allowed_actions"`
	ForbiddenActions     []string         `json:"forbidden_actions"`
	DataSensitivity      DataSensitivity  `json:"data_sensitivity"`
	DeterminismRequired  DeterminismLevel `json:"determinism_required"`
	Priority             Priority         `json:"priority"`
}

// ContextBlock holds contextual information attached to the intent.
type ContextBlock struct {
	SessionID   *string                `json:"session_id"`
	UserLocale  *string                `json:"user_locale"`
	Environment string                 `json:"environment"`
	Additional  map[string]interface{} `json:"additional"`
}

// CapabilityRequirement describes a required capability for this intent.
type CapabilityRequirement struct {
	CapabilityName     string      `json:"capability_name"`
	RequiredScopes     []string    `json:"required_scopes"`
	PreferredBinding   *BindingType `json:"preferred_binding"`
	MinimumTrustTier   TrustLevel  `json:"minimum_trust_tier"`
}

// TrustBlock holds trust and credential information.
type TrustBlock struct {
	DeclaredTrustLevel TrustLevel `json:"declared_trust_level"`
	DelegationChain    []string   `json:"delegation_chain"`
	TokenReference     *string    `json:"token_reference"`
}

// ProtocolBinding specifies how this intent should be bound to a protocol.
type ProtocolBinding struct {
	BindingType BindingType            `json:"binding_type"`
	Endpoint    *string                `json:"endpoint"`
	Metadata    map[string]interface{} `json:"metadata"`
}

// NegotiationHints provides optional hints to guide capability negotiation.
type NegotiationHints struct {
	CandidateCapabilities []string `json:"candidate_capabilities"`
	AllowFallback         bool     `json:"allow_fallback"`
	MaxCandidates         int      `json:"max_candidates"`
}

// IntegrityBlock holds integrity and provenance metadata.
type IntegrityBlock struct {
	SchemaVersion      string  `json:"schema_version"`
	Signed             bool    `json:"signed"`
	SignatureReference *string `json:"signature_reference"`
}

// ProvenanceBlock carries provenance and delegation metadata.
type ProvenanceBlock struct {
	Originator        *string    `json:"originator"`
	SubmittedBy       *string    `json:"submitted_by"`
	DelegationChain   []string   `json:"delegation_chain"`
	OnBehalfOf        *string    `json:"on_behalf_of"`
	DelegationPurpose *string    `json:"delegation_purpose"`
	DelegationExpiry  *time.Time `json:"delegation_expiry"`
	AuthorityScope    []string   `json:"authority_scope"`
}

// ---------------------------------------------------------------------------
// IntentEnvelope – the root SIP protocol object
// ---------------------------------------------------------------------------

// IntentEnvelope is the root SIP protocol object that carries a semantic
// intent from an actor to a target system.
type IntentEnvelope struct {
	SIPVersion            string                  `json:"sip_version"`
	MessageType           MessageType             `json:"message_type"`
	IntentID              string                  `json:"intent_id"`
	TraceID               string                  `json:"trace_id"`
	SpanID                string                  `json:"span_id"`
	Timestamp             time.Time               `json:"timestamp"`
	Actor                 ActorDescriptor         `json:"actor"`
	Target                TargetDescriptor        `json:"target"`
	Intent                IntentPayload           `json:"intent"`
	DesiredOutcome        DesiredOutcome          `json:"desired_outcome"`
	Constraints           Constraints             `json:"constraints"`
	Context               ContextBlock            `json:"context"`
	CapabilityRequirements []CapabilityRequirement `json:"capability_requirements"`
	Trust                 TrustBlock              `json:"trust"`
	ProtocolBindings      []ProtocolBinding       `json:"protocol_bindings"`
	Negotiation           NegotiationHints        `json:"negotiation"`
	Integrity             IntegrityBlock          `json:"integrity"`
	Provenance            *ProvenanceBlock        `json:"provenance"`
	Extensions            map[string]interface{}  `json:"extensions"`
}

// ---------------------------------------------------------------------------
// CapabilityDescriptor
// ---------------------------------------------------------------------------

// ProviderMetadata holds metadata about the capability provider.
type ProviderMetadata struct {
	ProviderID       string  `json:"provider_id"`
	ProviderName     string  `json:"provider_name"`
	Contact          *string `json:"contact"`
	Version          string  `json:"version"`
	DocumentationURL *string `json:"documentation_url"`
}

// SchemaReference describes the input or output schema for a capability.
type SchemaReference struct {
	SchemaID       *string           `json:"schema_id"`
	Description    string            `json:"description"`
	Properties     map[string]string `json:"properties"`
	RequiredFields []string          `json:"required_fields"`
}

// ExecutionMetadata describes the execution characteristics of a capability.
type ExecutionMetadata struct {
	AverageLatencyMs *int `json:"average_latency_ms"`
	Idempotent       bool `json:"idempotent"`
	SupportsDryRun   bool `json:"supports_dry_run"`
	MaxRetries       int  `json:"max_retries"`
}

// CapabilityConstraints describes operational constraints for a capability.
type CapabilityConstraints struct {
	RateLimitPerMinute    *int     `json:"rate_limit_per_minute"`
	RequiresHumanApproval bool     `json:"requires_human_approval"`
	AllowedEnvironments   []string `json:"allowed_environments"`
}

// CapabilityExample is an example invocation of the capability.
type CapabilityExample struct {
	Name                  string                 `json:"name"`
	Description           string                 `json:"description"`
	Parameters            map[string]interface{} `json:"parameters"`
	ExpectedOutputSummary string                 `json:"expected_output_summary"`
}

// CapabilityDescriptor fully describes a SIP-registered capability.
type CapabilityDescriptor struct {
	CapabilityID      string                 `json:"capability_id"`
	Name              string                 `json:"name"`
	Description       string                 `json:"description"`
	Provider          ProviderMetadata       `json:"provider"`
	IntentDomains     []string               `json:"intent_domains"`
	InputSchema       SchemaReference        `json:"input_schema"`
	OutputSchema      SchemaReference        `json:"output_schema"`
	OperationClass    OperationClass         `json:"operation_class"`
	RiskLevel         RiskLevel              `json:"risk_level"`
	RequiredScopes    []string               `json:"required_scopes"`
	MinimumTrustTier  TrustLevel             `json:"minimum_trust_tier"`
	SupportedBindings []BindingType          `json:"supported_bindings"`
	Execution         ExecutionMetadata      `json:"execution"`
	Constraints       CapabilityConstraints  `json:"constraints"`
	Examples          []CapabilityExample    `json:"examples"`
	Tags              []string               `json:"tags"`
	Extensions        map[string]interface{} `json:"extensions"`
}

// ---------------------------------------------------------------------------
// NegotiationResult
// ---------------------------------------------------------------------------

// RankedCandidate is a scored capability candidate produced during negotiation.
type RankedCandidate struct {
	Capability CapabilityDescriptor `json:"capability"`
	Score      float64              `json:"score"`
	Rationale  string               `json:"rationale"`
}

// PolicyDecisionSummary summarizes the policy evaluation result.
type PolicyDecisionSummary struct {
	Allowed          bool     `json:"allowed"`
	RequiresApproval bool     `json:"requires_approval"`
	DeniedScopes     []string `json:"denied_scopes"`
	PolicyNotes      []string `json:"policy_notes"`
}

// NegotiationResult is the output of SIP capability negotiation.
type NegotiationResult struct {
	IntentID               string                 `json:"intent_id"`
	RankedCandidates       []RankedCandidate      `json:"ranked_candidates"`
	SelectedCapability     *CapabilityDescriptor  `json:"selected_capability"`
	SelectionRationale     string                 `json:"selection_rationale"`
	RequiresClarification  bool                   `json:"requires_clarification"`
	ClarificationQuestions []string               `json:"clarification_questions"`
	AllowedBindings        []BindingType          `json:"allowed_bindings"`
	SelectedBinding        *BindingType           `json:"selected_binding"`
	PolicyDecision         PolicyDecisionSummary  `json:"policy_decision"`
	Extensions             map[string]interface{} `json:"extensions"`
}

// ---------------------------------------------------------------------------
// ExecutionPlan
// ---------------------------------------------------------------------------

// TraceMetadata holds trace information for an execution plan.
type TraceMetadata struct {
	TraceID      string  `json:"trace_id"`
	SpanID       string  `json:"span_id"`
	ParentSpanID *string `json:"parent_span_id"`
	IntentID     string  `json:"intent_id"`
}

// ExecutionStep is a single deterministic step in an execution plan.
type ExecutionStep struct {
	StepIndex    int                    `json:"step_index"`
	StepName     string                 `json:"step_name"`
	Description  string                 `json:"description"`
	CapabilityID string                 `json:"capability_id"`
	Binding      BindingType            `json:"binding"`
	Parameters   map[string]interface{} `json:"parameters"`
	DependsOn    []int                  `json:"depends_on"`
}

// PolicyCheckRecord records a policy check that was passed during planning.
type PolicyCheckRecord struct {
	CheckName string `json:"check_name"`
	Result    string `json:"result"`
	Notes     string `json:"notes"`
}

// ExecutionPlan is a deterministic execution plan produced by the SIP planner.
type ExecutionPlan struct {
	PlanID               string                 `json:"plan_id"`
	IntentID             string                 `json:"intent_id"`
	SelectedCapability   CapabilityDescriptor   `json:"selected_capability"`
	SelectedBinding      BindingType            `json:"selected_binding"`
	DeterministicTarget  map[string]interface{} `json:"deterministic_target"`
	GroundedParameters   map[string]interface{} `json:"grounded_parameters"`
	ExecutionSteps       []ExecutionStep        `json:"execution_steps"`
	PolicyChecksPassed   []PolicyCheckRecord    `json:"policy_checks_passed"`
	ApprovalRequired     bool                   `json:"approval_required"`
	Trace                TraceMetadata          `json:"trace"`
	ProvenanceSummary    map[string]interface{} `json:"provenance_summary"`
	Extensions           map[string]interface{} `json:"extensions"`
}

// ---------------------------------------------------------------------------
// AuditRecord
// ---------------------------------------------------------------------------

// AuditRecord is an immutable audit record for a processed SIP intent.
type AuditRecord struct {
	AuditID              string                 `json:"audit_id"`
	Timestamp            time.Time              `json:"timestamp"`
	TraceID              string                 `json:"trace_id"`
	IntentID             string                 `json:"intent_id"`
	ActorID              string                 `json:"actor_id"`
	ActorType            string                 `json:"actor_type"`
	IntentName           string                 `json:"intent_name"`
	IntentDomain         string                 `json:"intent_domain"`
	OperationClass       string                 `json:"operation_class"`
	SelectedCapabilityID *string                `json:"selected_capability_id"`
	SelectedBinding      *string                `json:"selected_binding"`
	ActionTaken          ActionTaken            `json:"action_taken"`
	PolicyAllowed        bool                   `json:"policy_allowed"`
	ApprovalState        string                 `json:"approval_state"`
	OutcomeSummary       OutcomeSummary         `json:"outcome_summary"`
	Notes                string                 `json:"notes"`
	Originator           *string                `json:"originator"`
	SubmittingActor      *string                `json:"submitting_actor"`
	DelegationChain      []string               `json:"delegation_chain"`
	Extensions           map[string]interface{} `json:"extensions"`
}
