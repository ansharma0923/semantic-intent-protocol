"""Risk-based policy decisioning for SIP.

Provides risk classification and rules that determine whether an operation
requires human approval or should be denied based on risk level, operation
class, and data sensitivity.
"""

from __future__ import annotations

from sip.envelope.models import DataSensitivity, OperationClass
from sip.registry.models import RiskLevel

# Combinations that require human approval when SIP_REQUIRE_APPROVAL_HIGH_RISK=true
_APPROVAL_REQUIRED_COMBINATIONS: set[tuple[RiskLevel, OperationClass]] = {
    (RiskLevel.HIGH, OperationClass.WRITE),
    (RiskLevel.HIGH, OperationClass.EXECUTE),
    (RiskLevel.HIGH, OperationClass.DELEGATE),
    (RiskLevel.CRITICAL, OperationClass.WRITE),
    (RiskLevel.CRITICAL, OperationClass.EXECUTE),
    (RiskLevel.CRITICAL, OperationClass.READ),
    (RiskLevel.CRITICAL, OperationClass.DELEGATE),
}

# Combinations that are always denied
_DENIED_COMBINATIONS: set[tuple[RiskLevel, DataSensitivity]] = {
    (RiskLevel.CRITICAL, DataSensitivity.RESTRICTED),
}


def requires_approval(
    risk_level: RiskLevel,
    operation_class: OperationClass,
    enforce_approval_policy: bool = True,
) -> bool:
    """Determine if human approval is required for the given risk+operation.

    Args:
        risk_level: The capability's risk level.
        operation_class: The operation being performed.
        enforce_approval_policy: When False, approval is never required
            (useful for non-production environments).

    Returns:
        True if approval is required.
    """
    if not enforce_approval_policy:
        return False
    return (risk_level, operation_class) in _APPROVAL_REQUIRED_COMBINATIONS


def is_denied_by_risk(
    risk_level: RiskLevel,
    data_sensitivity: DataSensitivity,
) -> bool:
    """Determine if the operation is outright denied based on risk + sensitivity.

    Args:
        risk_level: The capability's risk level.
        data_sensitivity: The data sensitivity classification.

    Returns:
        True if the operation should be denied.
    """
    return (risk_level, data_sensitivity) in _DENIED_COMBINATIONS
