from __future__ import annotations

from importlib import import_module
from typing import Any

__all__ = [
    "VPNAccess",
    "VPNAccessExpired",
    "VPNAccessNodeApply",
    "VPNAccessNodeRevisionEvidence",
    "VPNAccessNotFound",
    "VPNAccessState",
    "VPNAgentAuthenticationError",
    "VPNAgentContractError",
    "VPNAgentProtocolError",
    "VPNAgentRevisionConflict",
    "VPNAgentSnapshotOverflow",
    "VPNAgentStaleRevision",
    "VPNAgentTimeout",
    "VPNAgentTLSFailure",
    "VPNAgentTransportError",
    "VPNAgentUnavailable",
    "VPNFleetUnexpectedError",
    "VPNApplyStatus",
    "VPNAlert",
    "VPNMetric",
    "VPNObservation",
    "VPNDataPlaneState",
    "VPNCapacityUnavailable",
    "VPNNode",
    "VPNNodeHealthState",
    "VPNPurchase",
    "VPNRealityFingerprint",
    "VPNRealityFlow",
    "VPNReissueInProgress",
    "VPNReissueConflict",
    "VPNReissueNotEligible",
    "VPNRefundConflict",
    "VPNRefundPurchaseNotCurrent",
    "VPNSalesDisabled",
    "CollectVPNObservabilityService",
    "SafeVPNAlertService",
]

_EXPORT_MODULES = {
    "VPNAccess": "apps.vpn.models",
    "VPNAccessNodeApply": "apps.vpn.models",
    "VPNAccessNodeRevisionEvidence": "apps.vpn.models",
    "VPNNode": "apps.vpn.models",
    "VPNPurchase": "apps.vpn.models",
    "VPNAccessState": "apps.vpn.enums",
    "VPNApplyStatus": "apps.vpn.enums",
    "VPNAlert": "apps.vpn.observability",
    "VPNMetric": "apps.vpn.observability",
    "VPNObservation": "apps.vpn.observability",
    "VPNDataPlaneState": "apps.vpn.enums",
    "VPNNodeHealthState": "apps.vpn.enums",
    "VPNRealityFingerprint": "apps.vpn.enums",
    "VPNRealityFlow": "apps.vpn.enums",
    "VPNAccessExpired": "apps.vpn.exceptions",
    "VPNAccessNotFound": "apps.vpn.exceptions",
    "VPNAgentAuthenticationError": "apps.vpn.exceptions",
    "VPNAgentContractError": "apps.vpn.exceptions",
    "VPNAgentProtocolError": "apps.vpn.exceptions",
    "VPNAgentRevisionConflict": "apps.vpn.exceptions",
    "VPNAgentSnapshotOverflow": "apps.vpn.exceptions",
    "VPNAgentStaleRevision": "apps.vpn.exceptions",
    "VPNAgentTimeout": "apps.vpn.exceptions",
    "VPNAgentTLSFailure": "apps.vpn.exceptions",
    "VPNAgentTransportError": "apps.vpn.exceptions",
    "VPNAgentUnavailable": "apps.vpn.exceptions",
    "VPNFleetUnexpectedError": "apps.vpn.exceptions",
    "VPNCapacityUnavailable": "apps.vpn.exceptions",
    "VPNReissueInProgress": "apps.vpn.exceptions",
    "VPNReissueConflict": "apps.vpn.exceptions",
    "VPNReissueNotEligible": "apps.vpn.exceptions",
    "VPNRefundConflict": "apps.vpn.exceptions",
    "VPNRefundPurchaseNotCurrent": "apps.vpn.exceptions",
    "VPNSalesDisabled": "apps.vpn.exceptions",
    "CollectVPNObservabilityService": "apps.vpn.observability",
    "SafeVPNAlertService": "apps.vpn.observability",
}


def __getattr__(name: str) -> Any:
    """Resolve explicit public exports lazily while Django populates apps."""
    try:
        module_name = _EXPORT_MODULES[name]
    except KeyError as exc:
        raise AttributeError(name) from exc
    return getattr(import_module(module_name), name)
