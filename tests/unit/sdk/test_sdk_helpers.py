"""Tests for SDK identity and provenance helpers."""

from __future__ import annotations

from sip.sdk import (
    ActorType,
    TrustLevel,
    build_actor,
    build_intent_envelope,
    build_provenance,
)
from sip.sdk.helpers import (
    apply_identity_headers_to_envelope,
    compute_effective_scope_set,
    merge_identity_context,
    summarize_provenance,
)


class TestApplyIdentityHeaders:
    def _make_envelope(self) -> object:
        actor = build_actor(
            actor_id="original-actor",
            name="Original Actor",
            scopes=["sip:knowledge:read"],
            trust_level="internal",
        )
        return build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )

    def test_no_headers_returns_same_envelope(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope, {}, trusted=True  # type: ignore[arg-type]
        )
        assert result is envelope

    def test_actor_id_overridden(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope,  # type: ignore[arg-type]
            {"x-actor-id": "new-actor-id"},
            trusted=True,
        )
        assert result.actor.actor_id == "new-actor-id"
        assert result.actor.name == "Original Actor"

    def test_actor_type_overridden(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope,  # type: ignore[arg-type]
            {"x-actor-type": "human"},
            trusted=True,
        )
        assert result.actor.actor_type == ActorType.HUMAN

    def test_trust_level_overridden(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope,  # type: ignore[arg-type]
            {"x-trust-level": "privileged"},
            trusted=True,
        )
        assert result.actor.trust_level == TrustLevel.PRIVILEGED

    def test_scopes_overridden(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope,  # type: ignore[arg-type]
            {"x-scopes": "sip:knowledge:read, sip:data:write"},
            trusted=True,
        )
        assert "sip:knowledge:read" in result.actor.scopes
        assert "sip:data:write" in result.actor.scopes

    def test_untrusted_headers_ignored(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope,  # type: ignore[arg-type]
            {"x-actor-id": "attacker"},
            trusted=False,
        )
        assert result.actor.actor_id == "original-actor"

    def test_returns_new_envelope_when_changed(self) -> None:
        envelope = self._make_envelope()
        result = apply_identity_headers_to_envelope(
            envelope,  # type: ignore[arg-type]
            {"x-actor-id": "changed"},
            trusted=True,
        )
        assert result is not envelope
        assert envelope.actor.actor_id == "original-actor"  # type: ignore[union-attr]


class TestMergeIdentityContext:
    def test_no_change_returns_same(self) -> None:
        actor = build_actor(actor_id="a", name="A")
        result = merge_identity_context(actor, {}, trusted=True)
        assert result is actor

    def test_applies_header_overrides(self) -> None:
        actor = build_actor(actor_id="original", name="Original")
        result = merge_identity_context(
            actor, {"x-actor-name": "Updated"}, trusted=True
        )
        assert result.name == "Updated"


class TestComputeEffectiveScopeSet:
    def test_no_provenance_returns_actor_scopes(self) -> None:
        actor = build_actor(
            actor_id="svc",
            name="Svc",
            scopes=["sip:knowledge:read", "sip:data:write"],
        )
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )
        scopes = compute_effective_scope_set(envelope)
        assert scopes == frozenset(["sip:knowledge:read", "sip:data:write"])

    def test_with_authority_scope_returns_intersection(self) -> None:
        actor = build_actor(
            actor_id="agent",
            name="Agent",
            scopes=["sip:knowledge:read", "sip:data:write", "sip:admin:*"],
        )
        prov = build_provenance(
            originator="user-1",
            authority_scope=["sip:knowledge:read", "sip:data:write"],
        )
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            provenance=prov,
        )
        scopes = compute_effective_scope_set(envelope)
        # intersection: actor has all 3, authority_scope grants only 2
        assert scopes == frozenset(["sip:knowledge:read", "sip:data:write"])
        assert "sip:admin:*" not in scopes

    def test_no_overlap_returns_empty(self) -> None:
        actor = build_actor(
            actor_id="agent",
            name="Agent",
            scopes=["sip:knowledge:read"],
        )
        prov = build_provenance(
            originator="user-1",
            authority_scope=["sip:data:write"],
        )
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            provenance=prov,
        )
        scopes = compute_effective_scope_set(envelope)
        assert scopes == frozenset()


class TestSummarizeProvenance:
    def test_no_provenance_returns_empty_dict(self) -> None:
        actor = build_actor(actor_id="a", name="A")
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
        )
        summary = summarize_provenance(envelope)
        assert summary == {}

    def test_full_provenance_summary(self) -> None:
        actor = build_actor(actor_id="agent", name="Agent")
        prov = build_provenance(
            originator="user-1",
            submitted_by="agent",
            delegation_chain=["user-1", "agent-0"],
            on_behalf_of="user-1",
            delegation_purpose="automated workflow",
            authority_scope=["sip:knowledge:read"],
        )
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            provenance=prov,
        )
        summary = summarize_provenance(envelope)
        assert summary["originator"] == "user-1"
        assert summary["submitted_by"] == "agent"
        assert summary["delegation_chain"] == ["user-1", "agent-0"]
        assert summary["delegation_depth"] == 2
        assert summary["on_behalf_of"] == "user-1"
        assert summary["delegation_purpose"] == "automated workflow"
        assert summary["authority_scope"] == ["sip:knowledge:read"]

    def test_minimal_provenance(self) -> None:
        actor = build_actor(actor_id="a", name="A")
        prov = build_provenance(originator="u-1")
        envelope = build_intent_envelope(
            actor=actor,  # type: ignore[arg-type]
            intent_name="x",
            intent_domain="y",
            operation_class="read",
            outcome_summary="ok",
            provenance=prov,
        )
        summary = summarize_provenance(envelope)
        assert summary["originator"] == "u-1"
        assert summary["delegation_depth"] == 0
        assert "on_behalf_of" not in summary
