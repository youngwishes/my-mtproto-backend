from __future__ import annotations

from typing import ClassVar

from apps.core.exceptions import BaseInfraError, BaseServiceError


class VPNAgentTransportError(BaseInfraError):
    """VPN-agent временно недоступен"""

    error_code: ClassVar[str] = "agent_transport_error"

    def __init__(self, node_id: int) -> None:
        super().__init__(node_id, message=self.__doc__, error_code=self.error_code)


class VPNAgentTimeout(VPNAgentTransportError):
    error_code = "agent_timeout"


class VPNAgentTLSFailure(VPNAgentTransportError):
    error_code = "agent_tls_failure"


class VPNAgentAuthenticationError(VPNAgentTransportError):
    error_code = "agent_unauthorized"


class VPNAgentContractError(VPNAgentTransportError):
    error_code = "incompatible_contract"


class VPNAgentStaleRevision(VPNAgentTransportError):
    error_code = "stale_revision"


class VPNAgentRevisionConflict(VPNAgentTransportError):
    error_code = "revision_conflict"


class VPNAgentSnapshotOverflow(VPNAgentTransportError):
    error_code = "snapshot_too_large"


class VPNAgentProtocolError(VPNAgentTransportError):
    error_code = "agent_protocol_error"


class VPNAgentUnavailable(VPNAgentTransportError):
    error_code = "agent_unavailable"


class VPNFleetUnexpectedError(RuntimeError):
    """unexpected VPN fleet failure"""

    def __init__(self) -> None:
        super().__init__(self.__doc__)


class VPNAccessNotFound(BaseServiceError):
    """VPN-доступ не найден"""


class VPNAccessExpired(BaseServiceError):
    """Срок VPN-доступа истёк"""


class VPNReissueInProgress(BaseServiceError):
    """Перевыпуск VPN-доступа уже выполняется"""


class VPNCapacityUnavailable(BaseServiceError):
    """Сейчас нет доступных VPN-серверов"""


class VPNSalesDisabled(BaseServiceError):
    """Продажи VPN временно приостановлены"""
