from __future__ import annotations

from base64 import b64encode
from dataclasses import dataclass
from typing import TYPE_CHECKING, Callable, Iterable, final
from urllib.parse import quote

from apps.vpn.services.dtos import SubscriptionProfileDTO

if TYPE_CHECKING:
    from apps.vpn.models import VPNInstance, VPNSubscription


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class BuildSubscriptionService:
    """Строит HAPP subscription из уже полученных VPN-ноды и подписки."""

    shuffle_nodes: Callable[[list[VPNInstance]], None]

    def __call__(
        self,
        *,
        subscription: VPNSubscription,
        instances: Iterable[VPNInstance],
    ) -> str:
        ordered_instances = list(instances)
        self.shuffle_nodes(ordered_instances)
        profiles = [
            self._build_profile(subscription=subscription, instance=instance)
            for instance in ordered_instances
        ]
        uris = [
            uri
            for profile in profiles
            for uri in (profile.vless_uri, profile.hysteria2_uri)
        ]
        return b64encode("\n".join(uris).encode("utf-8")).decode("ascii")

    def _build_profile(
        self,
        *,
        subscription: VPNSubscription,
        instance: VPNInstance,
    ) -> SubscriptionProfileDTO:
        instance_name = self._encode(instance.name)
        vless_uri = (
            f"vless://{self._encode(subscription.vless_uuid)}@"
            f"{instance.public_host}:{instance.vless_port}?"
            "encryption=none&flow=xtls-rprx-vision&security=reality&"
            f"sni={self._encode(instance.reality_sni)}&fp=chrome&"
            f"pbk={self._encode(instance.reality_public_key)}&"
            f"sid={self._encode(instance.reality_short_id)}&type=tcp#"
            f"{instance_name}%20VLESS"
        )
        hysteria2_uri = (
            f"hysteria2://{self._encode(subscription.hysteria_secret)}@"
            f"{instance.public_host}:{instance.hysteria_port}/?"
            f"sni={self._encode(instance.hysteria_sni)}&obfs=salamander&"
            f"obfs-password={self._encode(instance.hysteria_obfs)}#"
            f"{instance_name}%20Hysteria2"
        )
        return SubscriptionProfileDTO(
            vless_uri=vless_uri,
            hysteria2_uri=hysteria2_uri,
        )

    @staticmethod
    def _encode(value: object) -> str:
        return quote(str(value), safe="")
