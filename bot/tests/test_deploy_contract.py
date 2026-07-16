from __future__ import annotations

from pathlib import Path

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
CANONICAL_FLAG_WIRING = 'VPN_SALES_ENABLED: "${VPN_SALES_ENABLED:-0}"'


def test_root_environment_is_the_single_vpn_sales_flag_source() -> None:
    root_example = (REPOSITORY_ROOT / ".env.example").read_text()
    bot_example = (REPOSITORY_ROOT / "bot/.env.example").read_text()

    assert root_example.count("VPN_SALES_ENABLED=0") == 1
    assert "VPN_SALES_ENABLED=" not in bot_example
    assert "VPN_SALES_ENABLED" in bot_example
    assert "root .env" in bot_example


def test_compose_injects_the_same_fail_closed_flag_into_bot() -> None:
    for filename in ("docker-compose.yml", "docker-compose.local.yml"):
        compose = (REPOSITORY_ROOT / filename).read_text()
        assert compose.count(CANONICAL_FLAG_WIRING) == 1
        assert compose.count("<<: *vpn-sales-environment") == 2
        assert "x-vpn-sales-environment: &vpn-sales-environment" in compose


def test_bot_example_contains_placeholders_not_secrets() -> None:
    bot_example = (REPOSITORY_ROOT / "bot/.env.example").read_text()

    assert "TELEGRAM_BOT_TOKEN=<BOT_TOKEN_FROM_BOTFATHER>" in bot_example
    assert "BOT_AUTH_TOKEN=<MATCH_ROOT_BOT_AUTH_TOKEN>" in bot_example
    assert "PROVIDER_TOKEN=<YUKASSA_PROVIDER_TOKEN>" in bot_example
