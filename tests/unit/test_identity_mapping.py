"""Unit tests for external identity header mapping (sip.broker.identity)."""

from __future__ import annotations

import pytest

from sip.broker.identity import (
    HEADER_ACTOR_ID,
    HEADER_ACTOR_NAME,
    HEADER_ACTOR_TYPE,
    HEADER_SCOPES,
    HEADER_TRUST_LEVEL,
    map_identity_headers,
)
from sip.envelope.models import ActorDescriptor, ActorType, TrustLevel


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_actor(
    actor_id: str = "actor-001",
    actor_type: ActorType = ActorType.AI_AGENT,
    name: str = "Test Agent",
    trust_level: TrustLevel = TrustLevel.INTERNAL,
    scopes: list[str] | None = None,
) -> ActorDescriptor:
    return ActorDescriptor(
        actor_id=actor_id,
        actor_type=actor_type,
        name=name,
        trust_level=trust_level,
        scopes=scopes or [],
    )


# ---------------------------------------------------------------------------
# Tests: trusted flag disabled
# ---------------------------------------------------------------------------


class TestIdentityMappingDisabled:
    def test_returns_original_actor_when_disabled(self) -> None:
        actor = _make_actor()
        headers = {
            HEADER_ACTOR_ID: "override-id",
            HEADER_ACTOR_NAME: "Override Name",
        }
        result = map_identity_headers(actor, headers, trusted=False)
        assert result is actor

    def test_ignores_all_headers_when_disabled(self) -> None:
        actor = _make_actor(actor_id="original")
        headers = {
            HEADER_ACTOR_ID: "injected-id",
            HEADER_ACTOR_TYPE: "human",
            HEADER_ACTOR_NAME: "Injected",
            HEADER_TRUST_LEVEL: "admin",
            HEADER_SCOPES: "sip:admin",
        }
        result = map_identity_headers(actor, headers, trusted=False)
        assert result.actor_id == "original"
        assert result.trust_level == TrustLevel.INTERNAL

    def test_env_var_disabled_by_default(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Trusted identity mapping must be off unless explicitly enabled."""
        monkeypatch.delenv("SIP_TRUSTED_IDENTITY_HEADERS", raising=False)
        actor = _make_actor()
        result = map_identity_headers(actor, {HEADER_ACTOR_ID: "hacked"})
        assert result.actor_id == actor.actor_id

    def test_env_var_false_disables_mapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIP_TRUSTED_IDENTITY_HEADERS", "false")
        actor = _make_actor()
        result = map_identity_headers(actor, {HEADER_ACTOR_ID: "hacked"})
        assert result.actor_id == actor.actor_id


# ---------------------------------------------------------------------------
# Tests: trusted flag enabled
# ---------------------------------------------------------------------------


class TestIdentityMappingEnabled:
    def test_no_headers_returns_original(self) -> None:
        actor = _make_actor()
        result = map_identity_headers(actor, {}, trusted=True)
        assert result is actor

    def test_actor_id_override(self) -> None:
        actor = _make_actor(actor_id="original-id")
        result = map_identity_headers(actor, {HEADER_ACTOR_ID: "new-id"}, trusted=True)
        assert result.actor_id == "new-id"

    def test_actor_type_override(self) -> None:
        actor = _make_actor(actor_type=ActorType.AI_AGENT)
        result = map_identity_headers(actor, {HEADER_ACTOR_TYPE: "human"}, trusted=True)
        assert result.actor_type == ActorType.HUMAN

    def test_actor_name_override(self) -> None:
        actor = _make_actor(name="Old Name")
        result = map_identity_headers(actor, {HEADER_ACTOR_NAME: "New Name"}, trusted=True)
        assert result.name == "New Name"

    def test_trust_level_override(self) -> None:
        actor = _make_actor(trust_level=TrustLevel.INTERNAL)
        result = map_identity_headers(
            actor, {HEADER_TRUST_LEVEL: "privileged"}, trusted=True
        )
        assert result.trust_level == TrustLevel.PRIVILEGED

    def test_scopes_override(self) -> None:
        actor = _make_actor(scopes=["sip:read"])
        result = map_identity_headers(
            actor, {HEADER_SCOPES: "sip:knowledge:read, sip:network:read"}, trusted=True
        )
        assert set(result.scopes) == {"sip:knowledge:read", "sip:network:read"}

    def test_multiple_headers_applied_together(self) -> None:
        actor = _make_actor()
        headers = {
            HEADER_ACTOR_ID: "gw-actor",
            HEADER_ACTOR_TYPE: "service",
            HEADER_ACTOR_NAME: "Gateway Service",
            HEADER_TRUST_LEVEL: "privileged",
            HEADER_SCOPES: "sip:admin,sip:knowledge:read",
        }
        result = map_identity_headers(actor, headers, trusted=True)
        assert result.actor_id == "gw-actor"
        assert result.actor_type == ActorType.SERVICE
        assert result.name == "Gateway Service"
        assert result.trust_level == TrustLevel.PRIVILEGED
        assert set(result.scopes) == {"sip:admin", "sip:knowledge:read"}

    def test_same_values_returns_original(self) -> None:
        """No override should occur when headers match existing values."""
        actor = _make_actor(actor_id="same-id", name="Same Name")
        headers = {HEADER_ACTOR_ID: "same-id", HEADER_ACTOR_NAME: "Same Name"}
        result = map_identity_headers(actor, headers, trusted=True)
        assert result is actor

    def test_invalid_actor_type_ignored(self) -> None:
        actor = _make_actor(actor_type=ActorType.AI_AGENT)
        result = map_identity_headers(
            actor, {HEADER_ACTOR_TYPE: "invalid_type"}, trusted=True
        )
        assert result.actor_type == ActorType.AI_AGENT

    def test_invalid_trust_level_ignored(self) -> None:
        actor = _make_actor(trust_level=TrustLevel.INTERNAL)
        result = map_identity_headers(
            actor, {HEADER_TRUST_LEVEL: "superadmin"}, trusted=True
        )
        assert result.trust_level == TrustLevel.INTERNAL

    def test_empty_actor_id_header_ignored(self) -> None:
        actor = _make_actor(actor_id="original")
        result = map_identity_headers(actor, {HEADER_ACTOR_ID: "  "}, trusted=True)
        assert result.actor_id == "original"

    def test_empty_scopes_header_ignored(self) -> None:
        actor = _make_actor(scopes=["sip:read"])
        result = map_identity_headers(actor, {HEADER_SCOPES: "   "}, trusted=True)
        assert result.scopes == ["sip:read"]

    def test_env_var_true_enables_mapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIP_TRUSTED_IDENTITY_HEADERS", "true")
        actor = _make_actor(actor_id="original")
        result = map_identity_headers(actor, {HEADER_ACTOR_ID: "from-env"})
        assert result.actor_id == "from-env"

    def test_env_var_1_enables_mapping(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setenv("SIP_TRUSTED_IDENTITY_HEADERS", "1")
        actor = _make_actor(actor_id="original")
        result = map_identity_headers(actor, {HEADER_ACTOR_ID: "from-env"})
        assert result.actor_id == "from-env"


# ---------------------------------------------------------------------------
# Tests: precedence (external headers override body actor fields)
# ---------------------------------------------------------------------------


class TestIdentityPrecedence:
    def test_header_overrides_body_actor_id(self) -> None:
        """Trusted header must win over body-provided actor_id."""
        body_actor = _make_actor(actor_id="body-actor")
        headers = {HEADER_ACTOR_ID: "header-actor"}
        result = map_identity_headers(body_actor, headers, trusted=True)
        assert result.actor_id == "header-actor"

    def test_header_overrides_body_trust_level(self) -> None:
        body_actor = _make_actor(trust_level=TrustLevel.PUBLIC)
        headers = {HEADER_TRUST_LEVEL: "privileged"}
        result = map_identity_headers(body_actor, headers, trusted=True)
        assert result.trust_level == TrustLevel.PRIVILEGED

    def test_header_overrides_body_scopes(self) -> None:
        body_actor = _make_actor(scopes=["sip:read"])
        headers = {HEADER_SCOPES: "sip:admin"}
        result = map_identity_headers(body_actor, headers, trusted=True)
        assert result.scopes == ["sip:admin"]

    def test_partial_override_preserves_other_fields(self) -> None:
        """Overriding one field must not affect unrelated fields."""
        body_actor = _make_actor(
            actor_id="keep-this",
            actor_type=ActorType.SERVICE,
            name="keep-name",
            trust_level=TrustLevel.PRIVILEGED,
            scopes=["sip:keep"],
        )
        # Only override the name
        result = map_identity_headers(
            body_actor, {HEADER_ACTOR_NAME: "new-name"}, trusted=True
        )
        assert result.actor_id == "keep-this"
        assert result.actor_type == ActorType.SERVICE
        assert result.name == "new-name"
        assert result.trust_level == TrustLevel.PRIVILEGED
        assert result.scopes == ["sip:keep"]
