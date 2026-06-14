"""Pytest-каркас интеграционного слоя.

Поднимает Django (ORM-доступ к живой БД, вариант A) и кладёт на sys.path:
- ``src/``  → backend-пакеты ``apps`` / ``config``
- ``bot/``  → пакет бота ``src`` (domain-клиенты ``src.domains.*``)
- репо-корень → пакет ``integration_tests``

Коллизии имён нет: top-level бота — ``src`` (из ``bot/``), backend — ``apps``/
``config`` (из ``src/``); сам каталог ``src/`` пакетом не импортируется.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

_PKG = Path(__file__).resolve().parent          # integration_tests/
_ROOT = _PKG.parent                              # репо-корень
_SRC = _ROOT / "src"                             # backend (apps, config)
_BOT = _ROOT / "bot"                             # бот (src.domains.*)

for _p in (str(_ROOT), str(_SRC), str(_BOT)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "integration_tests.settings")

import django  # noqa: E402

django.setup()

# ``django.setup()`` вставляет репо-корень в ``sys.path[0]``, из-за чего backend'овский
# каталог ``src/`` начинает перекрывать одноимённый top-level пакет бота (``bot/src``).
# Возвращаем ``bot/`` в начало пути, чтобы ``import src`` указывал на пакет бота
# (``apps``/``config`` бэкенда лежат в ``src/`` и доступны как top-level — им это не мешает).
while str(_BOT) in sys.path:
    sys.path.remove(str(_BOT))
sys.path.insert(0, str(_BOT))

# Закэшировать пакет бота как ``src`` в sys.modules ПОКА bot впереди пути.
# Дальше pytest при импорте каждого тест-модуля префиксит репо-корень в sys.path[0]
# (там backend'овский ``src/``), но раз ``src`` уже в кэше и его ``__path__`` = bot/src,
# любые ``import src.<...>`` бота продолжат резолвиться в bot, а не в backend.
import src  # noqa: E402,F401

import pytest_asyncio  # noqa: E402

from integration_tests import db, helpers  # noqa: E402


@pytest_asyncio.fixture
async def username():
    """Свежий синтетический telegram_id; гарантированная очистка БД+VDS после теста."""
    uid = helpers.make_test_id()
    await db.aw(db.cleanup_user)(uid)
    await helpers.vds_delete(uid)
    try:
        yield uid
    finally:
        await db.aw(db.cleanup_user)(uid)
        await helpers.vds_delete(uid)
