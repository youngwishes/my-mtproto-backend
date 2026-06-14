"""Django-настройки харнесса (вариант A: общий ORM + общая БД с контейнерами).

Берём боевые локальные настройки бэкенда (`config.settings`, которые сами
подхватывают репо-корневой `.env`) и переопределяем только путь к sqlite —
харнесс на хосте должен делить ТОТ ЖЕ файл, что и запущенные django/celery
контейнеры. Контейнеры монтируют репо-корневой `./data` в `/app/data`, поэтому
источник правды — `<repo>/data/db.sqlite3` (а НЕ `src/data/db.sqlite3`, который
использует хостовый `manage.py`).
"""

from __future__ import annotations

from pathlib import Path

from config.settings import *  # noqa: F401,F403

_REPO_ROOT = Path(__file__).resolve().parent.parent

DATABASES["default"]["NAME"] = str(_REPO_ROOT / "data" / "db.sqlite3")  # noqa: F405
