from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, final

import requests
from django.conf import settings
from django.core.exceptions import ImproperlyConfigured

from apps.vpn.services.dtos import NodeProfileDTO

if TYPE_CHECKING:
    from apps.vpn.models import VPNInstance


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class NodeClientService:
    """Выполняет защищённые idempotent запросы к VPN node-agent."""

    agent_token: str
    timeout: int

    def put_profile(self, *, instance: VPNInstance, profile: NodeProfileDTO) -> None:
        response = requests.put(
            url=self._profile_url(instance=instance, access_id=profile.access_id),
            headers=self._headers(),
            json={
                "vless_uuid": profile.vless_uuid,
                "hysteria_secret": profile.hysteria_secret,
            },
            timeout=self.timeout,
            allow_redirects=False,
        )
        self._ensure_success(response=response)

    def delete_profile(self, *, instance: VPNInstance, access_id: int) -> None:
        response = requests.delete(
            url=self._profile_url(instance=instance, access_id=access_id),
            headers=self._headers(),
            timeout=self.timeout,
            allow_redirects=False,
        )
        self._ensure_success(response=response)

    def check_health(self, *, instance: VPNInstance) -> None:
        response = requests.get(
            url=f"{instance.management_url.rstrip('/')}/health",
            headers=self._headers(),
            timeout=self.timeout,
            allow_redirects=False,
        )
        self._ensure_success(response=response)

    def _headers(self) -> dict[str, str]:
        return {"Authorization": f"Bearer {self.agent_token}"}

    @staticmethod
    def _profile_url(*, instance: VPNInstance, access_id: int) -> str:
        return f"{instance.management_url.rstrip('/')}/api/v1/profiles/{access_id}"

    @staticmethod
    def _ensure_success(*, response: requests.Response) -> None:
        if not 200 <= response.status_code < 300:
            raise requests.HTTPError(
                f"VPN node returned HTTP {response.status_code}",
                response=response,
            )


def get_node_client_service() -> NodeClientService:
    agent_token = settings.VPN_AGENT_TOKEN
    if not isinstance(agent_token, str) or not agent_token.strip():
        raise ImproperlyConfigured("VPN_AGENT_TOKEN must be configured")
    return NodeClientService(agent_token=agent_token, timeout=5)
