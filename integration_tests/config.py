"""Конфигурация интеграционного харнесса (всё через env, с дефолтами под локальный стенд).

Чёрнобоксовые e2e-тесты гоняются ТОЛЬКО против локального/стейдж-стека
(`docker-compose.local.yml`) с тестовой БД и локальным VDS. В прод — НЕЛЬЗЯ.
"""

from __future__ import annotations

import os

# --- Бэкенд (Django), куда стучатся domain-клиенты бота -----------------------
# django-контейнер из docker-compose.local.yml пробрасывает 8000 на хост.
BACKEND_URL: str = os.environ.get("INTEG_BACKEND_URL", "http://localhost:8000")

# --- VDS-инстансы -------------------------------------------------------------
# Хост-достижимые URL живых VDS (telemt-api) — харнесс по ним делает GET/DELETE
# для проверки фактического состояния секрета. Список через запятую.
VDS_VERIFY_URLS: list[str] = [
    u.strip()
    for u in os.environ.get("INTEG_VDS_VERIFY_URLS", "http://localhost:8080").split(",")
    if u.strip()
]

# Значение, которое пишем в VDSInstance.internal_ip_address / .port, чтобы
# celery-контейнер (сеть backend-стека) дотянулся до локального VDS.
# На Docker Desktop (macOS) хост виден контейнеру как host.docker.internal.
VDS_INTERNAL_IP: str = os.environ.get("INTEG_VDS_INTERNAL_IP", "host.docker.internal")
VDS_PORT: int = int(os.environ.get("INTEG_VDS_PORT", "8080"))

# --- Синтетические тестовые пользователи --------------------------------------
# Зарезервированный диапазон telegram_id (префикс 999000xxx), чтобы исключить
# коллизии с реальными Telegram ID. Подтверждено владельцем (2026-06-14).
TEST_ID_PREFIX: str = os.environ.get("INTEG_TEST_ID_PREFIX", "999")

# --- Ожидание async-доставки (Celery push_key_to_servers_task) -----------------
WAIT_TIMEOUT: float = float(os.environ.get("INTEG_WAIT_TIMEOUT", "10"))
WAIT_INTERVAL: float = float(os.environ.get("INTEG_WAIT_INTERVAL", "0.3"))

# Таймаут одиночного HTTP-запроса к бэкенду/VDS из харнесса.
HTTP_TIMEOUT: float = float(os.environ.get("INTEG_HTTP_TIMEOUT", "10"))
