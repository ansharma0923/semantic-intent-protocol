"""Shared fixtures for functional tests."""

from __future__ import annotations

import pytest

from sip.broker.service import BrokerService
from sip.policy.engine import PolicyEngine
from sip.registry.bootstrap import seed_registry
from sip.registry.service import CapabilityRegistryService


@pytest.fixture
def seeded_registry() -> CapabilityRegistryService:
    """Return a pre-seeded registry."""
    registry = CapabilityRegistryService()
    seed_registry(registry)
    return registry


@pytest.fixture
def broker(seeded_registry: CapabilityRegistryService) -> BrokerService:
    """Return a broker with a seeded registry and approval enforcement enabled."""
    engine = PolicyEngine(enforce_approval_policy=True)
    return BrokerService(registry=seeded_registry, policy_engine=engine)


@pytest.fixture
def broker_no_approval(seeded_registry: CapabilityRegistryService) -> BrokerService:
    """Return a broker with approval enforcement disabled (for simpler testing)."""
    engine = PolicyEngine(enforce_approval_policy=False)
    return BrokerService(registry=seeded_registry, policy_engine=engine)
