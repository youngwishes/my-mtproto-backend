from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, call, patch

import httpx

from . import config, db
from . import helpers


def test_default_vds_endpoint_is_remote_test_server() -> None:
    assert config.VDS_VERIFY_URLS == ["http://31.77.148.123:8080"]
    assert config.VDS_INTERNAL_IP == "31.77.148.123"
    assert config.VDS_PORT == 8080


def test_default_wait_covers_first_celery_retry() -> None:
    assert config.WAIT_TIMEOUT == 75


def test_ensure_test_vds_creates_complete_healthy_record() -> None:
    with (
        patch.object(db.VDSInstance.objects, "exclude") as exclude_vds,
        patch.object(db.VDSInstance.objects, "update_or_create") as update_or_create,
    ):
        update_or_create.return_value = (object(), True)
        db.ensure_test_vds()

    exclude_vds.assert_called_once_with(name="it-test")
    exclude_vds.return_value.update.assert_called_once_with(is_active=False)
    update_or_create.assert_called_once_with(
        name="it-test",
        defaults={
            "number": 99097,
            "ip_address": "31.77.148.123",
            "internal_ip_address": "31.77.148.123",
            "port": 8080,
            "is_healthy": True,
            "is_active": True,
            "location": "🧪 Test",
        },
    )


async def test_vds_polling_tolerates_transient_http_error() -> None:
    predicate = AsyncMock(
        side_effect=[httpx.RemoteProtocolError("server disconnected"), True]
    )

    assert await helpers.wait_until(predicate, timeout=0.1, interval=0) is True
    assert predicate.await_args_list == [call(), call()]


async def test_daily_removal_uses_remote_vds_timeout() -> None:
    with patch("subprocess.run") as run:
        await helpers.run_daily_removal()

    command = run.call_args.args[0]
    assert command[:5] == [
        "docker",
        "exec",
        "-e",
        "VDS_REQUEST_TIMEOUT=10",
        "django",
    ]


async def test_vds_get_retries_transient_http_error() -> None:
    response = httpx.Response(404)
    client = AsyncMock()
    client.get.side_effect = [httpx.ReadTimeout("slow VDS"), response]
    client_context = AsyncMock()
    client_context.__aenter__.return_value = client

    with patch.object(helpers.httpx, "AsyncClient", return_value=client_context):
        assert await helpers.vds_get("http://test-vds:8080", "999000001") is response

    assert client.get.await_count == 2


def test_local_compose_uses_integration_vds_timeout() -> None:
    compose = Path("docker-compose.local.yml").read_text()
    expected = 'VDS_REQUEST_TIMEOUT: "${INTEG_VDS_REQUEST_TIMEOUT:-10}"'
    assert compose.count(expected) == 2
