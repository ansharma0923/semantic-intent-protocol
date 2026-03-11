"""Capability discovery service for SIP brokers.

This module implements:

1. A ``DiscoveryRequest`` model for structured capability discovery queries.
2. A ``DiscoveryResponse`` model for the query result.
3. A ``DiscoveryService`` that handles local capability lookup and,
   optionally, remote peer discovery through the federation config.

Design notes:

* Discovery is always deterministic.
* Local capabilities are scored and ranked using the existing
  ``CapabilityRegistryService.find_matches`` logic.
* Remote discovery is performed by issuing HTTP ``POST /sip/capabilities/discover``
  requests to each configured peer.  Results are tagged with source broker metadata.
* Aggregation order: local candidates first (when ``prefer_local=True``), then
  remote candidates sorted by (trust_level_order DESC, score DESC, broker_id ASC).
* Remote capabilities from peers with trust_level < ROUTING are included in
  discovery results but tagged as ``routing_allowed=False``.
* All network calls use simple ``httpx`` requests with short timeouts.
* If a peer is unreachable and strict_mode is False, the error is logged and
  the peer is skipped.
"""

from __future__ import annotations

import logging
from typing import Any

from pydantic import BaseModel, Field

from sip.broker.federation import (
    FederationConfig,
    PeerTrustLevel,
    RemoteCapabilityResult,
)
from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.models import CapabilityDescriptor
from sip.registry.service import CapabilityRegistryService

logger = logging.getLogger(__name__)

# Peer trust level ordering for deterministic sort
_PEER_TRUST_ORDER = {
    PeerTrustLevel.DISCOVERY: 0,
    PeerTrustLevel.ROUTING: 1,
    PeerTrustLevel.FULL: 2,
}


# ---------------------------------------------------------------------------
# Request / response models
# ---------------------------------------------------------------------------


class DiscoveryRequest(BaseModel):
    """A structured capability discovery request.

    Fields are all optional; supply as many as are known to get better results.
    """

    intent_name: str | None = Field(
        default=None,
        description="Machine-readable intent name to match against (e.g. 'retrieve_document').",
    )
    intent_domain: str | None = Field(
        default=None,
        description="Functional domain to filter by (e.g. 'knowledge_management').",
    )
    operation_class: OperationClass | None = Field(
        default=None,
        description="Operation class to match.",
    )
    preferred_bindings: list[BindingType] = Field(
        default_factory=list,
        description="Preferred execution protocol bindings in order of preference.",
    )
    candidate_capabilities: list[str] = Field(
        default_factory=list,
        description="Hint: preferred capability IDs to consider first.",
    )
    trust_level: TrustLevel = Field(
        default=TrustLevel.INTERNAL,
        description="Trust level of the requesting actor (used for trust-tier filtering).",
    )
    max_results: int = Field(
        default=5,
        description="Maximum number of candidates to return.",
        ge=1,
        le=100,
    )
    include_remote: bool = Field(
        default=True,
        description="Whether to include remote (peer) capabilities in results.",
    )


class DiscoveryCandidate(BaseModel):
    """A single candidate returned by a discovery query."""

    capability_id: str
    name: str
    description: str
    operation_class: str
    supported_bindings: list[str]
    intent_domains: list[str]
    minimum_trust_tier: str
    score: float = Field(description="Relevance score (higher is better).")
    source_broker_id: str | None = Field(
        default=None,
        description="Broker ID that holds this capability (None = local).",
    )
    source_broker_url: str | None = Field(
        default=None,
        description="Broker URL for this capability (None = local).",
    )
    routing_allowed: bool = Field(
        default=True,
        description=(
            "Whether the local broker policy allows routing to this capability. "
            "False for remote capabilities from discovery-only peers."
        ),
    )
    discovery_path: list[str] = Field(
        default_factory=list,
        description="Broker IDs traversed during discovery.",
    )
    extensions: dict[str, Any] = Field(
        default_factory=dict,
        description="Extensions from the source capability descriptor.",
    )


class DiscoveryResponse(BaseModel):
    """Response to a capability discovery request."""

    candidates: list[DiscoveryCandidate] = Field(
        default_factory=list,
        description="Ranked capability candidates, best match first.",
    )
    total: int = Field(description="Total number of candidates returned.")
    local_count: int = Field(
        default=0,
        description="Number of local candidates.",
    )
    remote_count: int = Field(
        default=0,
        description="Number of remote (peer) candidates.",
    )
    peers_queried: list[str] = Field(
        default_factory=list,
        description="Broker IDs of peers that were queried.",
    )
    peers_failed: list[str] = Field(
        default_factory=list,
        description="Broker IDs of peers that failed to respond.",
    )


# ---------------------------------------------------------------------------
# Discovery service
# ---------------------------------------------------------------------------


class DiscoveryService:
    """Handles capability discovery for a SIP broker.

    Combines local registry lookup with optional peer broker queries when
    federation is configured.

    Args:
        registry: The local capability registry.
        federation: Optional federation configuration.  When None the service
            behaves as a pure local discovery service (v0.1 compatible).
        local_broker_id: Optional identifier for the local broker (used when
            tagging local results when federation is active).
    """

    def __init__(
        self,
        registry: CapabilityRegistryService,
        federation: FederationConfig | None = None,
        local_broker_id: str | None = None,
    ) -> None:
        self._registry = registry
        self._federation = federation
        self._local_broker_id = local_broker_id or (
            federation.broker_id if federation else None
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def discover(self, request: DiscoveryRequest) -> DiscoveryResponse:
        """Execute a discovery request and return ranked candidates.

        Local candidates are always evaluated.  Remote peers are queried
        only when ``federation`` is configured and
        ``request.include_remote`` is True.
        """
        local_candidates = self._discover_local(request)
        remote_results: list[RemoteCapabilityResult] = []
        peers_queried: list[str] = []
        peers_failed: list[str] = []

        if (
            self._federation is not None
            and request.include_remote
            and self._federation.discovery_peers()
        ):
            remote_results, peers_queried, peers_failed = self._discover_remote(request)

        candidates = self._aggregate(
            local_candidates=local_candidates,
            remote_results=remote_results,
            request=request,
        )

        # Trim to max_results
        candidates = candidates[: request.max_results]

        local_count = sum(1 for c in candidates if c.source_broker_id is None)
        remote_count = sum(1 for c in candidates if c.source_broker_id is not None)

        return DiscoveryResponse(
            candidates=candidates,
            total=len(candidates),
            local_count=local_count,
            remote_count=remote_count,
            peers_queried=peers_queried,
            peers_failed=peers_failed,
        )

    # ------------------------------------------------------------------
    # Local discovery
    # ------------------------------------------------------------------

    def _discover_local(
        self, request: DiscoveryRequest
    ) -> list[tuple[CapabilityDescriptor, float]]:
        """Query the local registry and return scored (cap, score) pairs."""
        intent_name = request.intent_name or ""
        intent_domain = request.intent_domain or ""

        if not intent_name and not intent_domain:
            # No query signals — return everything with score 0
            return [(cap, 0.0) for cap in self._registry.list_all()]

        from sip.registry.service import _TRUST_ORDER  # type: ignore[attr-defined]

        # Use the registry's find_matches for proper scoring
        preferred_binding = (
            request.preferred_bindings[0] if request.preferred_bindings else None
        )
        operation_class = request.operation_class

        if operation_class is None:
            # No operation class specified — try all capabilities with any signal
            # Fall back to a permissive search across both name and domain signals
            from sip.envelope.models import OperationClass as _OC

            best: dict[str, tuple[CapabilityDescriptor, float]] = {}
            for oc in _OC:
                matches = self._registry.find_matches(
                    intent_name=intent_name or ".",
                    intent_domain=intent_domain or ".",
                    operation_class=oc,
                    actor_trust=request.trust_level,
                    preferred_binding=preferred_binding,
                    candidate_ids=request.candidate_capabilities or None,
                    max_results=request.max_results * 2,
                )
                for cap, score in matches:
                    existing = best.get(cap.capability_id)
                    if existing is None or score > existing[1]:
                        best[cap.capability_id] = (cap, score)
            result = sorted(best.values(), key=lambda x: x[1], reverse=True)
            return result[: request.max_results * 2]

        return self._registry.find_matches(
            intent_name=intent_name or ".",
            intent_domain=intent_domain or ".",
            operation_class=operation_class,
            actor_trust=request.trust_level,
            preferred_binding=preferred_binding,
            candidate_ids=request.candidate_capabilities or None,
            max_results=request.max_results * 2,
        )

    # ------------------------------------------------------------------
    # Remote discovery
    # ------------------------------------------------------------------

    def _discover_remote(
        self, request: DiscoveryRequest
    ) -> tuple[list[RemoteCapabilityResult], list[str], list[str]]:
        """Query peer brokers and collect remote capability candidates.

        Returns a tuple of (remote_results, peers_queried, peers_failed).
        """
        try:
            import httpx
        except ImportError:
            logger.warning("httpx not available; skipping remote discovery")
            return [], [], []

        peers = self._federation.discovery_peers()  # type: ignore[union-attr]
        remote: list[RemoteCapabilityResult] = []
        queried: list[str] = []
        failed: list[str] = []

        payload = request.model_dump(mode="json")

        for peer in peers:
            queried.append(peer.broker_id)
            url = peer.broker_url.rstrip("/") + "/sip/capabilities/discover"
            try:
                resp = httpx.post(url, json=payload, timeout=5.0)
                resp.raise_for_status()
                data = resp.json()
                raw_candidates: list[dict] = data.get("candidates", [])
                for item in raw_candidates:
                    remote.append(
                        RemoteCapabilityResult(
                            source_broker_id=peer.broker_id,
                            source_broker_url=peer.broker_url,
                            peer_trust_level=peer.trust_level,
                            capability_data=item,
                            score=float(item.get("score", 0.0)),
                            discovery_path=[peer.broker_id]
                            + item.get("discovery_path", []),
                        )
                    )
            except Exception as exc:
                logger.warning(
                    "Peer discovery failed for broker '%s' at '%s': %s",
                    peer.broker_id,
                    url,
                    exc,
                )
                failed.append(peer.broker_id)
                if self._federation.strict_mode:  # type: ignore[union-attr]
                    raise RuntimeError(
                        f"Peer broker '{peer.broker_id}' is unavailable and "
                        "strict_mode is enabled."
                    ) from exc

        return remote, queried, failed

    # ------------------------------------------------------------------
    # Aggregation
    # ------------------------------------------------------------------

    def _aggregate(
        self,
        local_candidates: list[tuple[CapabilityDescriptor, float]],
        remote_results: list[RemoteCapabilityResult],
        request: DiscoveryRequest,
    ) -> list[DiscoveryCandidate]:
        """Combine local and remote candidates into a deterministically ordered list.

        Ordering rules:
        1. When ``prefer_local=True`` (default), local candidates come first.
        2. Remote candidates are sorted by (peer_trust_level DESC, score DESC,
           source_broker_id ASC) for determinism.
        3. When ``prefer_local=False``, all candidates are merged and sorted by
           score DESC, with local broker ID used as a tiebreaker.
        """
        prefer_local = (
            self._federation.prefer_local if self._federation else True
        )

        # Build local DiscoveryCandidates
        local_dc = [
            self._cap_to_candidate(cap, score) for cap, score in local_candidates
        ]

        # Build remote DiscoveryCandidates
        remote_dc = [
            self._remote_to_candidate(rr)
            for rr in sorted(
                remote_results,
                key=lambda r: (
                    -_PEER_TRUST_ORDER.get(r.peer_trust_level, 0),
                    -r.score,
                    r.source_broker_id,
                ),
            )
        ]

        if prefer_local:
            return local_dc + remote_dc

        # Merge and sort by score, local first on ties
        def sort_key(c: DiscoveryCandidate) -> tuple[float, str]:
            local_marker = "" if c.source_broker_id is None else "z"
            return (-c.score, local_marker + (c.source_broker_id or ""))

        return sorted(local_dc + remote_dc, key=sort_key)

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cap_to_candidate(
        self, cap: CapabilityDescriptor, score: float
    ) -> DiscoveryCandidate:
        return DiscoveryCandidate(
            capability_id=cap.capability_id,
            name=cap.name,
            description=cap.description,
            operation_class=cap.operation_class.value,
            supported_bindings=[b.value for b in cap.supported_bindings],
            intent_domains=list(cap.intent_domains),
            minimum_trust_tier=cap.minimum_trust_tier.value,
            score=score,
            source_broker_id=None,
            source_broker_url=None,
            routing_allowed=True,
            discovery_path=[self._local_broker_id] if self._local_broker_id else [],
            extensions=dict(cap.extensions),
        )

    def _remote_to_candidate(self, rr: RemoteCapabilityResult) -> DiscoveryCandidate:
        cap = rr.capability_data
        routing_allowed = rr.peer_trust_level in (
            PeerTrustLevel.ROUTING,
            PeerTrustLevel.FULL,
        )
        return DiscoveryCandidate(
            capability_id=cap.get("capability_id", ""),
            name=cap.get("name", ""),
            description=cap.get("description", ""),
            operation_class=cap.get("operation_class", ""),
            supported_bindings=cap.get("supported_bindings", []),
            intent_domains=cap.get("intent_domains", []),
            minimum_trust_tier=cap.get("minimum_trust_tier", "internal"),
            score=rr.score,
            source_broker_id=rr.source_broker_id,
            source_broker_url=rr.source_broker_url,
            routing_allowed=routing_allowed,
            discovery_path=rr.discovery_path,
            extensions=cap.get("extensions", {}),
        )
