from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import Mock

import requests
import responses
from django.test import SimpleTestCase, override_settings

from apps.vpn.dtos import VPNAgentNodeDTO, VPNExactSnapshotDTO
from apps.vpn.exceptions import (
    VPNAgentAuthenticationError,
    VPNAgentContractError,
    VPNAgentProtocolError,
    VPNAgentRevisionConflict,
    VPNAgentSnapshotOverflow,
    VPNAgentStaleRevision,
    VPNAgentTimeout,
    VPNAgentTLSFailure,
)
from apps.vpn.infra import VPNAgentTransport, VPNAgentTransportConfig
from apps.vpn.infra.agent_transport import get_vpn_agent_transport


CONTRACT_FIXTURES = (
    Path(__file__).parents[4]
    / "docs/features/vless-vpn-sales/contracts/fixtures"
)
REVIEWED_AGENT_SHA = "20ae654fc460163fe80aa82051ea9bb22f6d664a"
PINNED_XRAY_VERSION = "26.7.11"
PINNED_XRAY_DIGEST = (
    "sha256:a1644183accdb0b5be967093fe34be756fd5de15fe2ee0206e842ae17350967f"
)


def _node(
    *,
    node_id: int = 7,
    base_url: str = "https://agent-7.example.com",
    secret_key: str = "VPN_NODE_7_AGENT_TOKEN",
    contract_version: str = "v1",
) -> VPNAgentNodeDTO:
    return VPNAgentNodeDTO(
        node_id=node_id,
        base_url=base_url,
        secret_key=secret_key,
        contract_version=contract_version,
    )


def _health(**changes: object) -> dict[str, object]:
    payload: dict[str, object] = {
        "contract_version": "v1",
        "schema_version": "1.0",
        "agent_sha": REVIEWED_AGENT_SHA,
        "xray_version": PINNED_XRAY_VERSION,
        "xray_image_digest": PINNED_XRAY_DIGEST,
        "readiness": "READY",
        "applied_snapshot_revision": 7,
        "applied_snapshot_hash": "c" * 64,
    }
    payload.update(changes)
    return payload


def _transport(
    *, resolver: Mock | None = None, max_response_bytes: int = 65_536
) -> VPNAgentTransport:
    return VPNAgentTransport(
        session=requests.Session(),
        config=VPNAgentTransportConfig(
            expected_agent_sha=REVIEWED_AGENT_SHA,
            expected_xray_version=PINNED_XRAY_VERSION,
            expected_xray_image_digest=PINNED_XRAY_DIGEST,
            connect_timeout_seconds=1.5,
            read_timeout_seconds=4.0,
            expected_schema_version="1.0",
            max_response_bytes=max_response_bytes,
        ),
        resolve_secret=resolver or Mock(return_value="node-seven-token"),
    )


class VPNAgentTransportTests(SimpleTestCase):
    @responses.activate
    def test_health_uses_verified_https_scoped_auth_and_timeouts(self) -> None:
        resolver = Mock(return_value="node-seven-token")
        responses.get("https://agent-7.example.com/api/v1/health", json=_health())

        result = _transport(resolver=resolver).get_health(node=_node())

        self.assertEqual(result.contract_version, "v1")
        resolver.assert_called_once_with(secret_key="VPN_NODE_7_AGENT_TOKEN")
        request = responses.calls[0].request
        self.assertEqual(request.headers["Authorization"], "Bearer node-seven-token")
        self.assertEqual(request.headers["X-Agent-Contract-Version"], "v1")
        self.assertEqual(request.req_kwargs["timeout"], (1.5, 4.0))
        self.assertIs(request.req_kwargs["verify"], True)

    def test_session_disables_redirects_and_streams_bounded_response(self) -> None:
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.iter_content.return_value = (json.dumps(_health()).encode(),)
        session = Mock(spec=requests.Session)
        session.request.return_value = response
        transport = VPNAgentTransport(
            session=session,
            config=VPNAgentTransportConfig(
                expected_agent_sha=REVIEWED_AGENT_SHA,
                expected_xray_version=PINNED_XRAY_VERSION,
                expected_xray_image_digest=PINNED_XRAY_DIGEST,
            ),
            resolve_secret=Mock(return_value="token"),
        )

        transport.get_health(node=_node())

        request_kwargs = session.request.call_args.kwargs
        self.assertIs(request_kwargs["allow_redirects"], False)
        self.assertIs(request_kwargs["stream"], True)
        response.iter_content.assert_called_once_with(chunk_size=8_192)

    @responses.activate
    def test_plaintext_url_is_rejected_before_secret_lookup_or_network(self) -> None:
        resolver = Mock(return_value="secret")

        with self.assertRaises(VPNAgentTLSFailure):
            _transport(resolver=resolver).get_health(
                node=_node(base_url="http://agent-7.example.com")
            )

        resolver.assert_not_called()
        self.assertEqual(len(responses.calls), 0)

    @responses.activate
    def test_only_exact_https_origin_with_optional_port_is_accepted(self) -> None:
        responses.get("https://agent-7.example.com:8443/api/v1/health", json=_health())
        result = _transport().get_health(
            node=_node(base_url="https://agent-7.example.com:8443")
        )
        self.assertEqual(result.agent_sha, REVIEWED_AGENT_SHA)

        invalid_origins = (
            "https://agent-7.example.com/",
            "https://agent-7.example.com//",
            "https://agent-7.example.com/path",
            "https://user@agent-7.example.com",
            "https://agent-7.example.com?query=1",
            "https://agent-7.example.com#fragment",
            "https://agent-7.example.com:",
        )
        for origin in invalid_origins:
            with self.subTest(origin=origin):
                with self.assertRaises(VPNAgentTLSFailure):
                    _transport().get_health(node=_node(base_url=origin))
        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_get_redirects_are_never_followed(self) -> None:
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                responses.reset()
                responses.get(
                    "https://agent-7.example.com/api/v1/health",
                    status=status,
                    headers={
                        "Location": "https://attacker.example.com/api/v1/health",
                        "Content-Type": "application/json",
                    },
                    json={"code": "incompatible_contract", "message": "redirect"},
                )
                with self.assertRaises(VPNAgentProtocolError):
                    _transport().get_health(node=_node())
                self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_put_redirects_never_resend_snapshot(self) -> None:
        fixture = json.loads(
            (CONTRACT_FIXTURES / "canonical-empty.json").read_text()
        )
        snapshot = VPNExactSnapshotDTO.from_payload(fixture)
        for status in (301, 302, 307, 308):
            with self.subTest(status=status):
                responses.reset()
                responses.get(
                    "https://agent-7.example.com/api/v1/health", json=_health()
                )
                responses.put(
                    "https://agent-7.example.com/api/v1/snapshot",
                    status=status,
                    headers={
                        "Location": "https://attacker.example.com/api/v1/snapshot",
                        "Content-Type": "application/json",
                    },
                    json={"code": "incompatible_contract", "message": "redirect"},
                )
                with self.assertRaises(VPNAgentProtocolError):
                    _transport().put_snapshot(node=_node(), snapshot=snapshot)
                put_calls = [
                    call for call in responses.calls if call.request.method == "PUT"
                ]
                self.assertEqual(len(put_calls), 1)
                self.assertEqual(json.loads(put_calls[0].request.body), fixture)

    @responses.activate
    def test_each_node_resolves_only_its_own_token_on_each_request(self) -> None:
        secrets = {
            "VPN_NODE_7_AGENT_TOKEN": "token-seven-current",
            "VPN_NODE_8_AGENT_TOKEN": "token-eight",
        }
        resolver = Mock(side_effect=lambda *, secret_key: secrets[secret_key])
        responses.get("https://agent-7.example.com/api/v1/health", json=_health())
        responses.get("https://agent-8.example.com/api/v1/health", json=_health())
        transport = _transport(resolver=resolver)

        transport.get_health(node=_node())
        secrets["VPN_NODE_7_AGENT_TOKEN"] = "token-seven-next"
        transport.get_health(
            node=_node(
                node_id=8,
                base_url="https://agent-8.example.com",
                secret_key="VPN_NODE_8_AGENT_TOKEN",
            )
        )
        responses.get("https://agent-7.example.com/api/v1/health", json=_health())
        transport.get_health(node=_node())

        self.assertEqual(
            [call.request.headers["Authorization"] for call in responses.calls],
            [
                "Bearer token-seven-current",
                "Bearer token-eight",
                "Bearer token-seven-next",
            ],
        )

    @responses.activate
    def test_snapshot_metadata_matches_contract_without_accesses(self) -> None:
        responses.get(
            "https://agent-7.example.com/api/v1/snapshot",
            json={
                "contract_version": "v1",
                "schema_version": "1.0",
                "snapshot_revision": 7,
                "snapshot_hash": "c" * 64,
            },
        )

        result = _transport().get_snapshot(node=_node())

        self.assertEqual(result.snapshot_revision, 7)
        self.assertFalse(hasattr(result, "accesses"))

    @responses.activate
    def test_put_runs_compatible_health_preflight_and_sends_exact_fixture(self) -> None:
        fixture = json.loads(
            (CONTRACT_FIXTURES / "canonical-two-accesses.json").read_text()
        )
        snapshot = VPNExactSnapshotDTO.from_payload(fixture)
        responses.get("https://agent-7.example.com/api/v1/health", json=_health())
        responses.put(
            "https://agent-7.example.com/api/v1/snapshot",
            json={
                "schema_version": "1.0",
                "snapshot_revision": 7,
                "snapshot_hash": fixture["snapshot_hash"],
                "result": "applied",
            },
        )

        result = _transport().put_snapshot(node=_node(), snapshot=snapshot)

        self.assertEqual(result.result, "applied")
        self.assertEqual(len(responses.calls), 2)
        self.assertEqual(
            json.loads(responses.calls[1].request.body),
            fixture,
        )

    @responses.activate
    def test_mismatched_health_prevents_put(self) -> None:
        fixture = json.loads(
            (CONTRACT_FIXTURES / "canonical-empty.json").read_text()
        )
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            json=_health(contract_version="v2"),
        )

        with self.assertRaises(VPNAgentContractError):
            _transport().put_snapshot(
                node=_node(), snapshot=VPNExactSnapshotDTO.from_payload(fixture)
            )

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_unreviewed_runtime_identity_prevents_put(self) -> None:
        fixture = json.loads(
            (CONTRACT_FIXTURES / "canonical-empty.json").read_text()
        )
        mismatches: tuple[dict[str, Any], ...] = (
            {"agent_sha": "f" * 40},
            {"xray_version": "26.8.0"},
            {"xray_image_digest": f"sha256:{'f' * 64}"},
        )
        for mismatch in mismatches:
            with self.subTest(mismatch=tuple(mismatch)):
                responses.reset()
                responses.get(
                    "https://agent-7.example.com/api/v1/health",
                    json=_health(**mismatch),
                )
                with self.assertRaises(VPNAgentContractError):
                    _transport().put_snapshot(
                        node=_node(),
                        snapshot=VPNExactSnapshotDTO.from_payload(fixture),
                    )
                self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_unsupported_health_prevents_put(self) -> None:
        fixture = json.loads(
            (CONTRACT_FIXTURES / "canonical-empty.json").read_text()
        )
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            status=426,
            json={"code": "incompatible_contract", "message": "unsupported"},
        )

        with self.assertRaises(VPNAgentContractError):
            _transport().put_snapshot(
                node=_node(), snapshot=VPNExactSnapshotDTO.from_payload(fixture)
            )

        self.assertEqual(len(responses.calls), 1)

    @responses.activate
    def test_safe_status_mapping_never_includes_remote_message_or_token(self) -> None:
        cases = (
            (401, "unauthorized", VPNAgentAuthenticationError),
            (409, "stale_revision", VPNAgentStaleRevision),
            (409, "revision_conflict", VPNAgentRevisionConflict),
            (413, "snapshot_too_large", VPNAgentSnapshotOverflow),
            (426, "incompatible_contract", VPNAgentContractError),
        )
        secret = "token-must-never-leak"
        remote_message = "remote payload must never leak"
        for status, code, expected in cases:
            with self.subTest(status=status, code=code):
                responses.reset()
                responses.get(
                    "https://agent-7.example.com/api/v1/health",
                    status=status,
                    json={"code": code, "message": remote_message},
                )
                with self.assertRaises(expected) as caught:
                    _transport(resolver=Mock(return_value=secret)).get_health(node=_node())
                rendered = repr(caught.exception) + str(caught.exception)
                self.assertNotIn(secret, rendered)
                self.assertNotIn(remote_message, rendered)

    @responses.activate
    def test_unknown_or_malformed_response_is_protocol_error(self) -> None:
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            status=409,
            json={"code": "unexpected", "message": "unsafe"},
        )
        with self.assertRaises(VPNAgentProtocolError):
            _transport().get_health(node=_node())

        responses.reset()
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            status=401,
            json={
                "code": "unauthorized",
                "message": "safe",
                "unexpected": "private value",
            },
        )
        with self.assertRaises(VPNAgentProtocolError):
            _transport().get_health(node=_node())

    @responses.activate
    def test_json_content_type_is_required_for_success_and_error(self) -> None:
        for content_type in (None, "text/plain", "application/problem+json"):
            with self.subTest(content_type=content_type):
                responses.reset()
                headers = {} if content_type is None else {"Content-Type": content_type}
                responses.get(
                    "https://agent-7.example.com/api/v1/health",
                    body=json.dumps(_health()),
                    headers=headers,
                )
                with self.assertRaises(VPNAgentProtocolError):
                    _transport().get_health(node=_node())

                responses.reset()
                responses.get(
                    "https://agent-7.example.com/api/v1/health",
                    status=401,
                    body=json.dumps({"code": "unauthorized", "message": "unsafe"}),
                    headers=headers,
                )
                with self.assertRaises(VPNAgentProtocolError):
                    _transport().get_health(node=_node())

    @responses.activate
    def test_json_content_type_accepts_optional_utf8_charset(self) -> None:
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            body=json.dumps(_health()),
            headers={"Content-Type": "application/json; charset=utf-8"},
        )

        result = _transport().get_health(node=_node())

        self.assertEqual(result.agent_sha, REVIEWED_AGENT_SHA)

    @responses.activate
    def test_response_limit_rejects_actual_body_when_content_length_lies(self) -> None:
        body = json.dumps(_health())
        secret = "body-value-must-not-leak"
        body = body[:-1] + f', "extra": "{secret}"}}'
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            body=body,
            headers={
                "Content-Type": "application/json",
                "Content-Length": "1",
            },
        )

        with self.assertRaises(VPNAgentProtocolError) as caught:
            _transport(max_response_bytes=64).get_health(node=_node())

        self.assertNotIn(secret, repr(caught.exception) + str(caught.exception))

    @responses.activate
    def test_response_limit_rejects_declared_oversize_before_json(self) -> None:
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            body="{}",
            headers={
                "Content-Type": "application/json",
                "Content-Length": "4097",
            },
        )

        with self.assertRaises(VPNAgentProtocolError):
            _transport(max_response_bytes=4096).get_health(node=_node())

    def test_streamed_chunks_are_bounded_and_redacted(self) -> None:
        secret = "chunk-private-body"
        response = Mock(spec=requests.Response)
        response.status_code = 200
        response.headers = {"Content-Type": "application/json"}
        response.iter_content.return_value = (b'{"prefix":"', secret.encode(), b'"}')
        session = Mock(spec=requests.Session)
        session.request.return_value = response
        transport = VPNAgentTransport(
            session=session,
            config=VPNAgentTransportConfig(
                expected_agent_sha=REVIEWED_AGENT_SHA,
                expected_xray_version=PINNED_XRAY_VERSION,
                expected_xray_image_digest=PINNED_XRAY_DIGEST,
                max_response_bytes=8,
            ),
            resolve_secret=Mock(return_value="token"),
        )

        with self.assertRaises(VPNAgentProtocolError) as caught:
            transport.get_health(node=_node())

        self.assertNotIn(secret, repr(caught.exception) + str(caught.exception))
        response.close.assert_called_once_with()

    @responses.activate
    def test_oversized_error_body_is_rejected_without_value_leak(self) -> None:
        secret = "error-body-private-value"
        responses.get(
            "https://agent-7.example.com/api/v1/health",
            status=401,
            body=json.dumps({"code": "unauthorized", "message": secret * 10}),
            headers={"Content-Type": "application/json", "Content-Length": "1"},
        )

        with self.assertRaises(VPNAgentProtocolError) as caught:
            _transport(max_response_bytes=32).get_health(node=_node())

        self.assertNotIn(secret, repr(caught.exception) + str(caught.exception))

        responses.reset()
        responses.get("https://agent-7.example.com/api/v1/health", body="not-json")
        with self.assertRaises(VPNAgentProtocolError):
            _transport().get_health(node=_node())

    def test_timeout_and_tls_failures_are_safely_mapped(self) -> None:
        for failure, expected in (
            (requests.Timeout("token private detail"), VPNAgentTimeout),
            (requests.exceptions.SSLError("certificate private detail"), VPNAgentTLSFailure),
        ):
            with self.subTest(expected=expected):
                session = Mock(spec=requests.Session)
                session.request.side_effect = failure
                transport = VPNAgentTransport(
                    session=session,
                    config=VPNAgentTransportConfig(
                        expected_agent_sha=REVIEWED_AGENT_SHA,
                        expected_xray_version=PINNED_XRAY_VERSION,
                        expected_xray_image_digest=PINNED_XRAY_DIGEST,
                    ),
                    resolve_secret=Mock(return_value="secret"),
                )
                with self.assertRaises(expected) as caught:
                    transport.get_health(node=_node())
                self.assertNotIn("private detail", repr(caught.exception))

    def test_secret_resolver_failure_is_redacted(self) -> None:
        secret = "resolver-private-token"
        resolver = Mock(side_effect=RuntimeError(secret))

        with self.assertRaises(VPNAgentAuthenticationError) as caught:
            _transport(resolver=resolver).get_health(node=_node())

        rendered = repr(caught.exception) + str(caught.exception)
        self.assertNotIn(secret, rendered)

    @responses.activate
    def test_put_maps_stale_conflict_and_overflow_without_payload_leak(self) -> None:
        fixture = json.loads(
            (CONTRACT_FIXTURES / "canonical-empty.json").read_text()
        )
        snapshot = VPNExactSnapshotDTO.from_payload(fixture)
        cases = (
            (409, "stale_revision", VPNAgentStaleRevision),
            (409, "revision_conflict", VPNAgentRevisionConflict),
            (413, "snapshot_too_large", VPNAgentSnapshotOverflow),
        )
        for status, code, expected in cases:
            with self.subTest(code=code):
                responses.reset()
                responses.get(
                    "https://agent-7.example.com/api/v1/health", json=_health()
                )
                responses.put(
                    "https://agent-7.example.com/api/v1/snapshot",
                    status=status,
                    json={"code": code, "message": "uuid/private/token detail"},
                )
                with self.assertRaises(expected) as caught:
                    _transport().put_snapshot(node=_node(), snapshot=snapshot)
                self.assertNotIn("uuid/private/token", repr(caught.exception))

    @override_settings(
        VPN_AGENT_CONNECT_TIMEOUT_SECONDS=2.0,
        VPN_AGENT_READ_TIMEOUT_SECONDS=8.0,
        VPN_AGENT_SNAPSHOT_SCHEMA_VERSION="1.0",
        VPN_AGENT_EXPECTED_SHA=REVIEWED_AGENT_SHA,
        VPN_AGENT_EXPECTED_XRAY_VERSION=PINNED_XRAY_VERSION,
        VPN_AGENT_EXPECTED_XRAY_IMAGE_DIGEST=PINNED_XRAY_DIGEST,
        VPN_AGENT_MAX_RESPONSE_BYTES=4096,
    )
    def test_factory_wires_session_config_and_environment_resolver(self) -> None:
        transport = get_vpn_agent_transport()

        self.assertIsInstance(transport.session, requests.Session)
        self.assertEqual(transport.config.timeout, (2.0, 8.0))
        self.assertEqual(transport.config.expected_agent_sha, REVIEWED_AGENT_SHA)
        self.assertEqual(transport.config.expected_xray_version, PINNED_XRAY_VERSION)
        self.assertEqual(
            transport.config.expected_xray_image_digest, PINNED_XRAY_DIGEST
        )
        self.assertEqual(transport.config.max_response_bytes, 4096)
