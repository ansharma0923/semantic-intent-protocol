"""Persistent registry demo – save and reload capabilities from disk.

This example demonstrates:
  1. Creating a JsonFileCapabilityStore backed by a temporary JSON file.
  2. Seeding it with the standard SIP capabilities.
  3. Verifying the capabilities are persisted to disk.
  4. Reloading the capabilities in a fresh store instance.
  5. Registering a new custom capability and persisting it.

Run this script directly:

    python examples/persistent_registry_demo.py
"""

from __future__ import annotations

import json
import os
import tempfile
from pathlib import Path

from sip.envelope.models import BindingType, OperationClass, TrustLevel
from sip.registry.bootstrap import seed_registry
from sip.registry.models import (
    CapabilityDescriptor,
    ProviderMetadata,
    RiskLevel,
    SchemaReference,
)
from sip.registry.service import CapabilityRegistryService
from sip.registry.storage import JsonFileCapabilityStore

# ---------------------------------------------------------------------------
# Setup: use a temporary file so the demo is self-contained
# ---------------------------------------------------------------------------

tmpdir = tempfile.mkdtemp(prefix="sip_demo_")
caps_file = Path(tmpdir) / "capabilities.json"

print(f"Using capability file: {caps_file}")
print()

# ---------------------------------------------------------------------------
# Step 1 – Seed and persist
# ---------------------------------------------------------------------------

print("=== Step 1: Seed and persist capabilities ===")
store1 = JsonFileCapabilityStore(file_path=caps_file)
registry1 = CapabilityRegistryService(store=store1)
seed_registry(registry1)

print(f"Registered {registry1.count()} capabilities.")
print(f"File exists: {caps_file.exists()}")
print(f"File size: {caps_file.stat().st_size} bytes")
print()

# ---------------------------------------------------------------------------
# Step 2 – Reload in a fresh instance
# ---------------------------------------------------------------------------

print("=== Step 2: Reload in a fresh store instance ===")
store2 = JsonFileCapabilityStore(file_path=caps_file)
registry2 = CapabilityRegistryService(store=store2)

print(f"Reloaded {registry2.count()} capabilities.")
assert registry2.count() == registry1.count(), "Mismatch after reload!"
print("✓ Capability count matches original")

sample = registry2.get_by_id("retrieve_document")
assert sample is not None
print(f"✓ 'retrieve_document' capability loaded: {sample.name}")
print()

# ---------------------------------------------------------------------------
# Step 3 – Add a custom capability and reload
# ---------------------------------------------------------------------------

print("=== Step 3: Add custom capability and reload ===")

custom_cap = CapabilityDescriptor(
    capability_id="custom_report_generator",
    name="Custom Report Generator",
    description="Generates formatted reports from structured data.",
    provider=ProviderMetadata(
        provider_id="reporting_service",
        provider_name="Enterprise Reporting Service",
    ),
    intent_domains=["reporting", "data_export"],
    input_schema=SchemaReference(
        description="Report generation request",
        properties={"data": "object", "format": "string"},
        required_fields=["data"],
    ),
    output_schema=SchemaReference(
        description="Generated report",
        properties={"report_url": "string", "format": "string"},
    ),
    operation_class=OperationClass.ANALYZE,
    risk_level=RiskLevel.LOW,
    required_scopes=["sip:knowledge:read"],
    minimum_trust_tier=TrustLevel.INTERNAL,
    supported_bindings=[BindingType.REST],
)

registry2.register(custom_cap)
print(f"Registered custom capability: {custom_cap.capability_id}")
print(f"Total capabilities now: {registry2.count()}")

# Reload again
store3 = JsonFileCapabilityStore(file_path=caps_file)
registry3 = CapabilityRegistryService(store=store3)

assert registry3.get_by_id("custom_report_generator") is not None
print(f"✓ Custom capability reloaded after restart")
print(f"Total after reload: {registry3.count()}")
print()

# ---------------------------------------------------------------------------
# Step 4 – Inspect the JSON file
# ---------------------------------------------------------------------------

print("=== Step 4: Inspect the JSON file ===")
raw = json.loads(caps_file.read_text())
print(f"JSON file contains {len(raw)} entries.")
first = raw[0]
print(f"First entry fields: {list(first.keys())}")
print()

# ---------------------------------------------------------------------------
# Cleanup
# ---------------------------------------------------------------------------

caps_file.unlink()
os.rmdir(tmpdir)
print("Demo complete. Temporary files cleaned up.")
