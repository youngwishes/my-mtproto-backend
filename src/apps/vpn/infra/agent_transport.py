from __future__ import annotations

from dataclasses import dataclass
import json
import os
import re
from typing import Any, final
from urllib.parse import urlsplit

from django.conf import settings
import requests

from apps.vpn.dtos import (
    VPNAgentApplyResultDTO,
    VPNAgentHealthDTO,
    VPNAgentNodeDTO,
    VPNAgentSnapshotMetadataDTO,
    VPNExactSnapshotDTO,
)
from apps.vpn.exceptions import (
    VPNAgentAuthenticationError,
    VPNAgentContractError,
    VPNAgentProtocolError,
    VPNAgentRevisionConflict,
    VPNAgentSnapshotOverflow,
    VPNAgentStaleRevision,
    VPNAgentTimeout,
    VPNAgentTLSFailure,
    VPNAgentUnavailable,
)
from apps.vpn.protocols import VPNAgentSecretResolver

_SHA1 = re.compile(r"^[0-9a-f]{40}$")
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IMAGE_DIGEST = re.compile(r"^sha256:[0-9a-f]{64}$")
_READINESS = {"READY", "NOT_READY", "RECOVERY_READY"}
_JSON_CONTENT_TYPE = re.compile(
    r'^application/json(?:\s*;\s*charset=(?:utf-8|"utf-8"))?$', re.IGNORECASE
)


@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAgentTransportConfig:
    expected_agent_sha: str
    expected_xray_version: str
    expected_xray_image_digest: str
    connect_timeout_seconds: float = 2.0
    read_timeout_seconds: float = 10.0
    expected_schema_version: str = "1.0"
    max_response_bytes: int = 65_536

    @property
    def timeout(self) -> tuple[float, float]:
        return (self.connect_timeout_seconds, self.read_timeout_seconds)


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VPNAgentTransport:
    session: requests.Session
    config: VPNAgentTransportConfig
    resolve_secret: VPNAgentSecretResolver

    def get_health(self, *, node: VPNAgentNodeDTO) -> VPNAgentHealthDTO:
        response = self._request(node=node, method="GET", path="/api/v1/health")
        payload = self._success_payload(node=node, response=response)
        expected_keys = {
            "contract_version",
            "schema_version",
            "agent_sha",
            "xray_version",
            "xray_image_digest",
            "readiness",
            "applied_snapshot_revision",
            "applied_snapshot_hash",
        }
        if (
            set(payload) != expected_keys
            or payload.get("contract_version") != node.contract_version
            or payload.get("schema_version") != self.config.expected_schema_version
            or payload.get("agent_sha") != self.config.expected_agent_sha
            or payload.get("xray_version") != self.config.expected_xray_version
            or payload.get("xray_image_digest")
            != self.config.expected_xray_image_digest
            or not isinstance(payload.get("agent_sha"), str)
            or not _SHA1.fullmatch(payload["agent_sha"])
            or not isinstance(payload.get("xray_version"), str)
            or not payload["xray_version"]
            or not isinstance(payload.get("xray_image_digest"), str)
            or not _IMAGE_DIGEST.fullmatch(payload["xray_image_digest"])
            or payload.get("readiness") not in _READINESS
            or not self._valid_optional_snapshot_pair(
                revision=payload.get("applied_snapshot_revision"),
                snapshot_hash=payload.get("applied_snapshot_hash"),
            )
        ):
            raise VPNAgentContractError(node.node_id)
        return VPNAgentHealthDTO(**payload)

    def get_snapshot(self, *, node: VPNAgentNodeDTO) -> VPNAgentSnapshotMetadataDTO:
        response = self._request(node=node, method="GET", path="/api/v1/snapshot")
        payload = self._success_payload(node=node, response=response)
        if (
            set(payload)
            != {
                "contract_version",
                "schema_version",
                "snapshot_revision",
                "snapshot_hash",
            }
            or payload.get("contract_version") != node.contract_version
            or payload.get("schema_version") != self.config.expected_schema_version
            or not self._valid_optional_snapshot_pair(
                revision=payload.get("snapshot_revision"),
                snapshot_hash=payload.get("snapshot_hash"),
            )
        ):
            raise VPNAgentContractError(node.node_id)
        return VPNAgentSnapshotMetadataDTO(**payload)

    def put_snapshot(
        self, *, node: VPNAgentNodeDTO, snapshot: VPNExactSnapshotDTO
    ) -> VPNAgentApplyResultDTO:
        self.get_health(node=node)
        if snapshot.schema_version != self.config.expected_schema_version:
            raise VPNAgentContractError(node.node_id)
        response = self._request(
            node=node,
            method="PUT",
            path="/api/v1/snapshot",
            json_payload=snapshot.as_payload(),
        )
        payload = self._success_payload(node=node, response=response)
        if (
            set(payload)
            != {"schema_version", "snapshot_revision", "snapshot_hash", "result"}
            or payload.get("schema_version") != snapshot.schema_version
            or payload.get("snapshot_revision") != snapshot.snapshot_revision
            or payload.get("snapshot_hash") != snapshot.snapshot_hash
            or payload.get("result") not in {"applied", "no_op"}
        ):
            raise VPNAgentProtocolError(node.node_id)
        return VPNAgentApplyResultDTO(**payload)

    def _request(
        self,
        *,
        node: VPNAgentNodeDTO,
        method: str,
        path: str,
        json_payload: dict[str, Any] | None = None,
    ) -> requests.Response:
        base_url = node.base_url
        try:
            parsed = urlsplit(base_url)
            parsed_port = parsed.port
        except ValueError:
            raise VPNAgentTLSFailure(node.node_id) from None
        if (
            parsed.scheme != "https"
            or not parsed.hostname
            or parsed.username
            or parsed.password
            or parsed.query
            or parsed.fragment
            or parsed.path
            or parsed_port is None and ":" in parsed.netloc.rsplit("]", 1)[-1]
            or any(character.isspace() for character in base_url)
        ):
            raise VPNAgentTLSFailure(node.node_id)
        try:
            token = self.resolve_secret(secret_key=node.secret_key)
        except Exception:
            raise VPNAgentAuthenticationError(node.node_id) from None
        if not isinstance(token, str) or not token.strip():
            raise VPNAgentAuthenticationError(node.node_id)
        try:
            return self.session.request(
                method,
                base_url + path,
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Agent-Contract-Version": node.contract_version,
                    "Accept": "application/json",
                },
                json=json_payload,
                timeout=self.config.timeout,
                verify=True,
                allow_redirects=False,
                stream=True,
            )
        except requests.exceptions.SSLError:
            raise VPNAgentTLSFailure(node.node_id) from None
        except requests.Timeout:
            raise VPNAgentTimeout(node.node_id) from None
        except requests.RequestException:
            raise VPNAgentUnavailable(node.node_id) from None

    def _success_payload(
        self, *, node: VPNAgentNodeDTO, response: requests.Response
    ) -> dict[str, Any]:
        payload = self._read_response_payload(node=node, response=response)
        if response.status_code != 200:
            self._raise_for_error(
                node=node,
                status_code=response.status_code,
                payload=payload,
            )
        if not isinstance(payload, dict):
            raise VPNAgentProtocolError(node.node_id)
        return payload

    def _raise_for_error(
        self,
        *,
        node: VPNAgentNodeDTO,
        status_code: int,
        payload: object,
    ) -> None:
        if (
            not isinstance(payload, dict)
            or set(payload) != {"code", "message"}
            or not isinstance(payload.get("code"), str)
            or not isinstance(payload.get("message"), str)
        ):
            raise VPNAgentProtocolError(node.node_id)
        code = payload["code"]
        exception_by_outcome = {
            (401, "unauthorized"): VPNAgentAuthenticationError,
            (409, "stale_revision"): VPNAgentStaleRevision,
            (409, "revision_conflict"): VPNAgentRevisionConflict,
            (413, "snapshot_too_large"): VPNAgentSnapshotOverflow,
            (426, "incompatible_contract"): VPNAgentContractError,
        }
        exception = exception_by_outcome.get((status_code, code))
        if exception is None:
            raise VPNAgentProtocolError(node.node_id)
        raise exception(node.node_id)

    def _read_response_payload(
        self, *, node: VPNAgentNodeDTO, response: requests.Response
    ) -> object:
        try:
            content_type = response.headers.get("Content-Type", "")
            if _JSON_CONTENT_TYPE.fullmatch(content_type.strip()) is None:
                raise VPNAgentProtocolError(node.node_id)
            declared_length = response.headers.get("Content-Length")
            if declared_length is not None:
                normalized_length = declared_length.strip()
                if (
                    not normalized_length.isdecimal()
                    or int(normalized_length) > self.config.max_response_bytes
                ):
                    raise VPNAgentProtocolError(node.node_id)
            chunks: list[bytes] = []
            size = 0
            try:
                for chunk in response.iter_content(
                    chunk_size=min(8_192, self.config.max_response_bytes + 1)
                ):
                    if not chunk:
                        continue
                    size += len(chunk)
                    if size > self.config.max_response_bytes:
                        raise VPNAgentProtocolError(node.node_id)
                    chunks.append(chunk)
            except requests.RequestException:
                raise VPNAgentUnavailable(node.node_id) from None
            try:
                return json.loads(b"".join(chunks).decode("utf-8"))
            except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
                raise VPNAgentProtocolError(node.node_id) from None
        finally:
            response.close()

    @staticmethod
    def _valid_optional_snapshot_pair(
        *, revision: object, snapshot_hash: object
    ) -> bool:
        if revision is None or snapshot_hash is None:
            return revision is None and snapshot_hash is None
        return (
            isinstance(revision, int)
            and not isinstance(revision, bool)
            and revision >= 1
            and isinstance(snapshot_hash, str)
            and _SHA256.fullmatch(snapshot_hash) is not None
        )


def resolve_vpn_agent_secret_from_environment(*, secret_key: str) -> str:
    value = os.environ.get(secret_key)
    if value is None or not value.strip():
        return ""
    return value.strip()


def get_vpn_agent_transport() -> VPNAgentTransport:
    return VPNAgentTransport(
        session=requests.Session(),
        config=VPNAgentTransportConfig(
            expected_agent_sha=settings.VPN_AGENT_EXPECTED_SHA,
            expected_xray_version=settings.VPN_AGENT_EXPECTED_XRAY_VERSION,
            expected_xray_image_digest=(
                settings.VPN_AGENT_EXPECTED_XRAY_IMAGE_DIGEST
            ),
            connect_timeout_seconds=settings.VPN_AGENT_CONNECT_TIMEOUT_SECONDS,
            read_timeout_seconds=settings.VPN_AGENT_READ_TIMEOUT_SECONDS,
            expected_schema_version=settings.VPN_AGENT_SNAPSHOT_SCHEMA_VERSION,
            max_response_bytes=settings.VPN_AGENT_MAX_RESPONSE_BYTES,
        ),
        resolve_secret=resolve_vpn_agent_secret_from_environment,
    )
