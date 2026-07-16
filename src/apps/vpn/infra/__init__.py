from __future__ import annotations

from importlib import import_module
from typing import Any

from apps.vpn.infra.single_writer import FileSingleWriterLock
from apps.vpn.infra.worker_health import (
    VPNPaymentWorkerHealthCheck,
    read_process_command,
)
from apps.vpn.infra.subscription_throttle import (
    RedisVPNSubscriptionThrottle,
    get_subscription_throttle,
)

__all__ = [
    "FileSingleWriterLock",
    "VPNAgentTransport",
    "VPNAgentTransportConfig",
    "VPNPaymentWorkerHealthCheck",
    "get_vpn_agent_transport",
    "read_process_command",
    "RedisVPNSubscriptionThrottle",
    "get_subscription_throttle",
    "resolve_vpn_agent_secret_from_environment",
]

_LAZY_AGENT_EXPORTS = {
    "VPNAgentTransport",
    "VPNAgentTransportConfig",
    "get_vpn_agent_transport",
    "resolve_vpn_agent_secret_from_environment",
}


def __getattr__(name: str) -> Any:
    """Keep raw worker subprocess imports independent from Django setup."""
    if name not in _LAZY_AGENT_EXPORTS:
        raise AttributeError(name)
    return getattr(import_module("apps.vpn.infra.agent_transport"), name)
