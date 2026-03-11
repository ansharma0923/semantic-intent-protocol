"""Federation model for SIP distributed brokers.

This module provides the configuration types and data models for multi-broker
SIP federation.  Federation in this phase focuses on:

* Broker trust relationships
* Remote capability visibility
* Provenance preservation across broker boundaries
* Policy controls for remote discovery and routing

Design principles:

* Federation is **opt-in**.  A broker without federation config behaves exactly
  as it did in v0.1.
* Local broker remains the **final authority** for authorization and planning.
* Remote capabilities from untrusted peers are **rejected** before planning.
* Provenance metadata is **preserved** when capabilities cross broker boundaries.
* Everything is deterministic and testable with no external dependencies.
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, Field


# ---------------------------------------------------------------------------
# Peer trust levels
# ---------------------------------------------------------------------------


class PeerTrustLevel(str, Enum):
    """Trust level assigned to a federated peer broker.

    Levels are ordered from least to most privileged:

    * ``DISCOVERY`` – peer capabilities may be returned in discovery results.
      The local broker will not route execution to peer capabilities.
    * ``ROUTING``   – peer capabilities may be used for routing decisions
      (included in execution plans), but not for full execution delegation.
    * ``FULL``      – peer is fully trusted for discovery, routing, and
      execution delegation metadata.
    """

    DISCOVERY = "discovery"
    ROUTING = "routing"
    FULL = "full"


# ---------------------------------------------------------------------------
# Federated peer descriptor
# ---------------------------------------------------------------------------


class FederatedPeer(BaseModel):
    """Describes a trusted peer broker in the federation.

    Each peer has an identity, a reachable URL, and a trust level that
    controls how much of the peer's capabilities are accepted.
    """

    broker_id: str = Field(
        description="Unique identifier for the peer broker.", min_length=1
    )
    broker_url: str = Field(
        description="Base URL of the peer broker's HTTP API.", min_length=1
    )
    trust_level: PeerTrustLevel = Field(
        default=PeerTrustLevel.DISCOVERY,
        description="Trust level granted to this peer.",
    )
    description: str = Field(
        default="",
        description="Optional human-readable description of this peer.",
    )
    metadata: dict[str, Any] = Field(
        default_factory=dict,
        description="Additional peer metadata.",
    )


# ---------------------------------------------------------------------------
# Federation configuration
# ---------------------------------------------------------------------------


class FederationConfig(BaseModel):
    """Federation configuration for a SIP broker.

    When a broker is configured with federation, it can forward discovery
    requests to peer brokers and aggregate remote capability candidates with
    its own local candidates.

    Policy rules:

    * Only peers whose ``trust_level`` is >= ``DISCOVERY`` are queried.
    * Peers with ``trust_level == DISCOVERY`` cannot have their capabilities
      included in execution plans.
    * Peers with ``trust_level >= ROUTING`` may have their capabilities
      included in execution plans (as routing targets).
    * ``prefer_local`` (default True) ensures local capabilities sort before
      remote capabilities at equal score.
    * ``strict_mode`` (default False) causes discovery to fail fast if any
      peer is unavailable.  When False, peer failures are logged and skipped.
    """

    broker_id: str = Field(
        description="Unique identifier for this broker.", min_length=1
    )
    broker_url: str = Field(
        description="Public base URL of this broker's HTTP API.", min_length=1
    )
    peers: list[FederatedPeer] = Field(
        default_factory=list,
        description="List of trusted peer brokers.",
    )
    prefer_local: bool = Field(
        default=True,
        description=(
            "When True, local capabilities are preferred over remote capabilities "
            "at equal relevance score."
        ),
    )
    strict_mode: bool = Field(
        default=False,
        description=(
            "When True, discovery fails if any peer is unavailable. "
            "When False, peer failures are logged and skipped."
        ),
    )

    def get_peer(self, broker_id: str) -> FederatedPeer | None:
        """Return the peer with the given broker_id, or None."""
        for peer in self.peers:
            if peer.broker_id == broker_id:
                return peer
        return None

    def discovery_peers(self) -> list[FederatedPeer]:
        """Return all peers that may be queried for discovery."""
        return [p for p in self.peers if p.trust_level in (
            PeerTrustLevel.DISCOVERY, PeerTrustLevel.ROUTING, PeerTrustLevel.FULL
        )]

    def routing_peers(self) -> list[FederatedPeer]:
        """Return peers whose capabilities may be included in execution plans."""
        return [p for p in self.peers if p.trust_level in (
            PeerTrustLevel.ROUTING, PeerTrustLevel.FULL
        )]


# ---------------------------------------------------------------------------
# Remote capability result
# ---------------------------------------------------------------------------


class RemoteCapabilityResult(BaseModel):
    """A capability candidate returned by a remote peer broker.

    Wraps the raw capability descriptor JSON with provenance metadata
    that records which peer broker provided this capability.
    """

    source_broker_id: str = Field(
        description="ID of the broker that provided this capability."
    )
    source_broker_url: str = Field(
        description="URL of the broker that provided this capability."
    )
    peer_trust_level: PeerTrustLevel = Field(
        description="Trust level of the source broker at the time of discovery."
    )
    capability_data: dict[str, Any] = Field(
        description="Raw capability descriptor as returned by the peer."
    )
    score: float = Field(
        default=0.0,
        description="Relevance score assigned by the peer broker.",
    )
    discovery_path: list[str] = Field(
        default_factory=list,
        description=(
            "Ordered list of broker IDs through which this capability was "
            "discovered.  The originating broker is first."
        ),
    )
