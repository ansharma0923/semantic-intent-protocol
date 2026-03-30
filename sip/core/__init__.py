"""SIP Core – internal canonical models and pipeline.

This package contains the internal canonical layer of SIP:

* ``normalized_intent`` – NormalizedIntent model and from_envelope adapter
* ``fail_closed`` – explicit fail-closed checks and structured denials
* ``decision_bundle`` – DecisionBundle output model
* ``pipeline`` – SIPPipeline orchestrator
* ``policy_engine`` – CanonicalPolicyEngine implementing PolicyEngineInterface
* ``deterministic_planner`` – DeterministicPlanner that works from externally
  supplied candidate capabilities

All types in this package are internal.  External callers should continue to
use ``IntentEnvelope`` as the entry point and receive ``DecisionBundle`` as
the output.
"""

from sip.core.decision_bundle import DecisionBundle
from sip.core.deterministic_planner import DeterministicPlanner
from sip.core.fail_closed import FailClosedError, StructuredDenial
from sip.core.normalized_intent import NormalizedIntent, from_envelope
from sip.core.pipeline import SIPPipeline
from sip.core.policy_engine import CanonicalPolicyEngine
from sip.policy.interface import PolicyEngineInterface, PolicyResult

__all__ = [
    "CanonicalPolicyEngine",
    "DecisionBundle",
    "DeterministicPlanner",
    "FailClosedError",
    "NormalizedIntent",
    "PolicyEngineInterface",
    "PolicyResult",
    "SIPPipeline",
    "StructuredDenial",
    "from_envelope",
]
