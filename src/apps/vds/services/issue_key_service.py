from __future__ import annotations

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING, final

from django.conf import settings

from apps.vds.exceptions import KeysLimitReached
from apps.vds.models import MTPRotoKey
from apps.vds.selectors import count_active_valid_keys, get_keys_by_username
from apps.vds.tasks import push_key_to_servers_task

if TYPE_CHECKING:
    from datetime import datetime

    from apps.users.models import SystemUser


@final
@dataclass(kw_only=True, slots=True, frozen=True)
class IssueKeyService:
    """Выдаёт новый MTPRoto-ключ: чистая запись в БД + асинхронная доставка.

    Сервер не выбирается и синхронных HTTP-запросов нет — секрет валиден на всём
    флоте, доставка на здоровые VDS происходит таском push_key_to_servers_task.
    """

    def __call__(
        self,
        *,
        user: SystemUser,
        expired_date: datetime,
    ) -> MTPRotoKey:
        if count_active_valid_keys() >= settings.GLOBAL_KEYS_LIMIT:
            raise KeysLimitReached(telegram_id=str(user.username))

        # инвариант «одна строка на юзера»: сносим прежние ключи перед выдачей
        get_keys_by_username(username=str(user.username)).delete()

        key = MTPRotoKey.objects.create(
            user=user,
            token=os.urandom(16).hex(),
            expired_date=expired_date,
        )
        push_key_to_servers_task.delay(key_id=key.pk)
        return key


def get_issue_key_service() -> IssueKeyService:
    return IssueKeyService()
