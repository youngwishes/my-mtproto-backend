# MTPRotoKey: переход на reconcile-модель (БД как источник правды)

**Date:** 2026-06-14
**Status:** Approved

## Проблема

Ключи реплицируются на **все** активные VDS-инстансы, то есть серверы — функциональные зеркала: каждый обслуживает всех пользователей. При этом модель `MTPRotoKey` несёт рудименты «одного домашнего сервера»:

- FK `MTPRotoKey.vds` указывает на один «домашний» VDS;
- `node_number` / `get_proxy_link()` строят **одну дефолтную** ссылку на этот домашний сервер;
- `VDSInstance.get_least_populated()` выбирает «наименее загруженный» сервер через `Count("keys")`.

Эти механизмы измеряют искусственную метрику: раз каждый ключ реплицируется везде, реальная нагрузка на все серверы одинакова, а `get_least_populated` балансирует лишь то, какой субдомен попадёт в дефолтную ссылку. Раз серверов несколько и они равноправны, выбор «дефолтного» сервера смысла не имеет, а вместе с ним теряет смысл и `get_proxy_link()`.

`tls_domain` хранится per-key, хотя на всём флоте он одинаков (подтверждено): это домен маскировки FakeTLS, зашитый в секрет через `get_secret_token()`. Его не следует путать с субдоменом сервера `{name}.beatvault.ru` (хост в URL) — тот у каждого VDS свой (`kz`, `nl`, …), и им заведует `VDSInstance.name`.

## Цель

Переосмыслить модель: **`MTPRotoKey` — это один секрет, валидный на всём флоте, без понятия «домашний сервер».** Выдача ключа — чистая запись в БД; доставка секрета на серверы — отдельный механизм. БД становится единственным источником правды, серверы — производным кэшом.

## Ключевые ограничения / факты

- Секрет (`token`) — случайный hex, идемпотентно принимается VDS (`POST /api/users`, `409 → PATCH/skip`).
- `tls_domain` (домен маскировки FakeTLS внутри секрета, через `get_secret_token()`) одинаков на всех VDS (подтверждено владельцем). Переезжает в `settings.TLS_DOMAIN`.
- `VDSInstance.name` — DNS-субдомен сервера в хосте proxy-URL (`{name}.beatvault.ru`), у каждого VDS свой (`kz`, `nl`, …). Это **другой** домен, не путать с `tls_domain`.
- Инвариант: **активный ключ должен присутствовать на всех здоровых VDS.**
- Ссылки на все серверы уже генерятся на лету в `GetMyServersService` — это и есть единственный канал доставки ссылок пользователю.

## Выбранный подход: declarative reconcile + мгновенный пинок

Желаемое состояние = строки `MTPRotoKey` в БД. Любое расхождение с реальностью на серверах устраняет reconcile-проход «для ключа K обеспечить присутствие на всех здоровых серверах».

| Сценарий | Действие | Триггер |
|---|---|---|
| Выдача / обновление | создать/обновить строку в БД → запушить **этот** ключ на все здоровые серверы | мгновенный celery-пинок |
| Отзыв / истечение | удалить секрет ключа со всех здоровых серверов | мгновенный пинок + дневной `RemoveExpiredKeysDailyService` (без изменений) |
| Восстановление упавшего VDS | бэкфилл всех активных ключей на поднявшийся сервер | существующий `check_vds_health_task → sync_keys_to_vds_task` (без изменений) |

Выдача ключа **не делает синхронных HTTP-запросов и не выбирает сервер** — только пишет в БД и ставит таск.

### Что НЕ входит в эту задачу (осознанно отложено)

- **Периодический страховочный reconcile.** Отдельная задача. Там на стороне VDS появится GET-эндпоинт со списком активных пользователей, бэкенд будет сверять списки и до-досылать только отсутствующих (дифф вместо «всё на всех»: 300 ключей × 4 сервера = 1200 POST/мин — неприемлемо).
- **Известный пробел:** новый добавленный VDS (`is_healthy=True` сразу) не получит существующие ключи автоматически — триггера sync для него нет. Закроется будущей reconcile-задачей. Фиксируется здесь как ограничение.

## Изменения модели

### `MTPRotoKey` (`src/apps/vds/models.py`)

Удалить:
- FK `vds` (миграция: `RemoveField`)
- `node_number` (миграция: `RemoveField`)
- `tls_domain` (миграция: `RemoveField`) — переезжает в `settings.TLS_DOMAIN`
- метод `get_proxy_link()` (дефолтная одиночная ссылка)

Изменить:
- `get_secret_token()` — брать домен из `settings.TLS_DOMAIN` вместо `self.tls_domain`
- `get_proxy_link_for_server(server_name)` → переименовать в `get_proxy_link(*, server_name)` — единственный генератор ссылок
- `__str__` — больше не зовёт `get_proxy_link()`; вернуть нейтральное, напр. `f"MTPRotoKey #{self.pk} — {self.user_id}"`

### `VDSInstance` (`src/apps/vds/models.py`)

Удалить:
- поле `user_limit` (миграция: `RemoveField`)
- метод `is_available()`
- `VDSQuerySet.order_by_population()` и `get_least_populated()`

Глобальный лимит активных ключей — `settings.GLOBAL_KEYS_LIMIT`, проверяется в `IssueKeyService`.

## Изменения сервисов

### Удаляются (синхронная провизия + репликация больше не нужны)

- `AddNewKeyInfraService` (`add_new_key_infra_service.py`)
- `ReplicateKeyAddToServerInfraService` (`replicate_key_add_to_server_infra_service.py`)
- `ReplicateKeyUpdateToServerInfraService` (`replicate_key_update_to_server_infra_service.py`)
- таски: `add_key_to_another_vds_instances_task`, `replicate_key_add_to_server_task`, `update_key_on_another_vds_instances_task`, `replicate_key_update_to_server_task`

### `IssueKeyService` (`issue_key_service.py`)

```python
def __call__(self, *, user, expired_date):
    if count_active_valid_keys() >= settings.GLOBAL_KEYS_LIMIT:
        raise KeysLimitReached(telegram_id=str(user.username))
    key = MTPRotoKey.objects.create(
        user=user,
        token=os.urandom(16).hex(),
        expired_date=expired_date,
    )
    push_key_to_servers_task.delay(key_id=key.pk)
    return key
```

Никакого `get_least_populated_vds`, никакого синхронного POST, никакого `vds`/`node_number`/`tls_domain` при создании.

### `UpdateKeyService` (`update_key_service.py`)

- убрать `get_least_populated_vds`, выбор сервера;
- сгенерить новый `token`, сохранить (`update_fields` без `vds`/`node_number`/`tls_domain`);
- поставить `push_key_to_servers_task.delay(key_id=...)`;
- `UpdateKeyOut` больше **не содержит** `link`.

### Доставка ключа — новый таск + сервис

- `push_key_to_servers_task(key_id)` — для каждого здорового VDS идемпотентный POST секрета; ретраи + пометка `is_healthy=False` через существующий `_handle_replication_failure`.
- `remove_key_from_servers_task(key_id)` (или переиспользовать существующий remove-infra) — мгновенный пинок на удаление при отзыве.
- Базовый инфра-блок переиспользует логику `SyncKeysToVdsInfraService` (он остаётся для бэкфилла при восстановлении сервера).

### `migrate` / `sync`

- `get_vds_instance_keys()` ломается без FK → удалить селектор.
- `SyncKeysToVdsInfraService` уже использует `get_all_active_valid_keys()` — без изменений.
- `MigrateVdsKeysInfraService` использует `get_vds_instance_keys(source)` → переключить на `get_all_active_valid_keys()` (либо удалить как дублирующий `sync`; решить при реализации, по умолчанию — переключить на `get_all_active_valid_keys`).

## Изменения селекторов (`src/apps/vds/selectors.py`)

- удалить `get_least_populated_vds()`
- удалить `get_vds_instance_keys()`
- добавить `count_active_valid_keys() -> int` (для глобального лимита)

## Бот / контракты

Везде, где сейчас уходит одиночная ссылка через `get_proxy_link()`, — заменить на кнопку «📡 Мои серверы» (`callback_data="my_servers"`, хендлер уже есть: `bot/src/handlers/links.py:25`).

| Точка | Было | Стало |
|---|---|---|
| `FirstFreeLinkService` → `IssuedKeyOut` | `link=key.get_proxy_link()` | убрать `link` из DTO; бот показывает кнопку «Мои серверы» |
| `GetFreeLinkViaReferralsService` | `link=...` | то же |
| `UpdateKeyService` → `UpdateKeyOut` | `link=...` | то же |
| `notifications/resolvers.py::_resolve_active_key_link` | `{"link": key.get_proxy_link()}` | resolver и `ContextResolverType.ACTIVE_KEY_LINK` удалить; шаблоны → `button_callback_data="my_servers"` |
| `BroadcastProxyLinksService` | `url=key.get_proxy_link()` | `callback_data="my_servers"` |

`GetMyServersService` — без изменений (уже генерит ссылки на лету).

## Settings

- `TLS_DOMAIN: str` — значение взять из текущих прод-данных (одинаково на всех VDS).
- `GLOBAL_KEYS_LIMIT: int` — потолок активных валидных ключей.

## Миграции

1. Схема: `RemoveField` `MTPRotoKey.vds`, `MTPRotoKey.node_number`, `MTPRotoKey.tls_domain`, `VDSInstance.user_limit`.
2. Данные (ручная заметка, до удаления `tls_domain`): убедиться, что `settings.TLS_DOMAIN` совпадает со значением в существующих строках.
3. Данные шаблонов: `NotificationTemplate` с `button_url`-ссылкой на ключ → `button_callback_data="my_servers"`, `button_url` очистить (правится в админке, без кода).

## Тесты (TDD — сначала тесты)

Переписать (упадут):
- `apps/users/tests/test_first_free_link.py` — без `link`, без `vds`
- `apps/users/tests/test_update_key_view.py`, `apps/vds/tests/test_services/test_update_key_service.py` — без `link`/`vds`/`node_number`
- `apps/users/tests/test_get_referral_link_view.py`
- `apps/notifications/tests/test_resolvers.py` — resolver удалён
- `apps/vds/tests/test_models.py` — удалить тесты `get_least_populated`/`get_proxy_link`; добавить `get_proxy_link(server_name)` через `settings.TLS_DOMAIN`
- `apps/payments/tests/...`, нотификейшн-тесты с `vds=` в фабриках

Новые:
- `IssueKeyService`: создаёт строку без HTTP/без сервера; ставит `push_key_to_servers_task`; глобальный лимит → `KeysLimitReached`
- `push_key_to_servers_task` / инфра доставки: пуш на все здоровые серверы, идемпотентность, пометка нездоровым при провале
- `count_active_valid_keys`
- DTO `IssuedKeyOut` / `UpdateKeyOut` без `link`

Фабрики (`apps/vds/tests/factories.py`): убрать `vds = SubFactory(...)`, `node_number`, `tls_domain`.

## Документация

- `docs/MODELS.md` — убрать `MTPRotoKey.vds`/`node_number`/`tls_domain`, `VDSInstance.user_limit`
- `docs/ARCHITECTURE.md` — reconcile-модель, нет «домашнего сервера», глобальный лимит, `TLS_DOMAIN` в settings
- `docs/CONTRACTS.md` — DTO без `link`, доставка через «Мои серверы»
- `docs/BUSINESS.md` — выдача = запись в БД + асинхронная доставка
- `CLAUDE.md` — обновить разделы про `get_least_populated`, `user_limit`, репликацию, per-key `tls_domain`

## Файлы

**Удалить:**
- `src/apps/vds/services/add_new_key_infra_service.py`
- `src/apps/vds/services/replicate_key_add_to_server_infra_service.py`
- `src/apps/vds/services/replicate_key_update_to_server_infra_service.py`
- соответствующие тесты удалённых сервисов

**Создать:**
- инфра-сервис/таск доставки одного ключа на все здоровые серверы (`push_key_to_servers...`)
- тесты доставки и `IssueKeyService`

**Изменить:**
- `src/apps/vds/models.py` — чистка `MTPRotoKey`/`VDSInstance`, `get_secret_token` на `settings.TLS_DOMAIN`, переименование метода
- `src/apps/vds/services/issue_key_service.py`, `update_key_service.py`
- `src/apps/vds/services/migrate_keys_infra_service.py` — на `get_all_active_valid_keys`
- `src/apps/vds/tasks.py` — удалить replicate-таски, добавить push/remove-таски
- `src/apps/vds/selectors.py` — `-get_least_populated_vds`, `-get_vds_instance_keys`, `+count_active_valid_keys`
- `src/apps/users/services/first_free_link_service.py`, `get_free_link_via_referrals.py` — DTO без `link`
- `src/apps/users/services/dtos.py` (`IssuedKeyOut`), `apps/vds/services/dtos/...` (`UpdateKeyOut`)
- `src/apps/notifications/resolvers.py`, `enums.py` — удалить `ACTIVE_KEY_LINK`
- `src/apps/notifications/services/broadcast_proxy_links_service.py` — кнопка на `callback_data`
- `src/config/settings/...` — `TLS_DOMAIN`, `GLOBAL_KEYS_LIMIT`
- миграции `apps/vds`
- тесты и фабрики (см. выше)
- бот: хендлеры free/referral/update — показывать кнопку «Мои серверы» вместо ссылки (точные файлы уточнить при реализации)
- `docs/*`, `CLAUDE.md`

## План реализации (порядок шагов)

Каждый шаг — TDD (сначала тесты), в конце `make test` зелёный. Принцип порядка: **сначала добавляем новое и переключаемся на него, в самом конце сносим старое и дропаем колонки** — так сборка зелёная на любом промежуточном шаге. После каждого шага — остановка на ревью.

1. **Settings** — `TLS_DOMAIN`, `GLOBAL_KEYS_LIMIT`. Без смены поведения.
2. **Модель, без дропа колонок** — `get_secret_token()` на `settings.TLS_DOMAIN`; переименовать `get_proxy_link_for_server` → `get_proxy_link(*, server_name)`; `__str__` нейтральный (`f"MTPRotoKey #{self.pk} — {self.user_id}"`).
3. **Новая доставка** — селектор `count_active_valid_keys`; инфра-сервис + celery-таск `push_key_to_servers` (идемпотентный POST на все здоровые серверы, ретраи + пометка `is_healthy=False` через существующий `_handle_replication_failure`). Переиспользовать логику `SyncKeysToVdsInfraService`.
4. **Перепроводка выдачи/обновления** — `IssueKeyService`/`UpdateKeyService` на «запись в БД + пинок `push_key_to_servers_task`»; проверка `GLOBAL_KEYS_LIMIT` → `KeysLimitReached`; убрать `get_least_populated`.
5. **Контракты/бот** — `IssuedKeyOut`/`UpdateKeyOut` без `link`; free/referral/update/broadcast → кнопка `my_servers`; удалить resolver `ACTIVE_KEY_LINK` + enum-значение; шаблоны на `button_callback_data`.
6. **Удаление мёртвого** — `AddNewKeyInfraService`, `Replicate{Add,Update}…` сервисы + их таски (`add_key_to_another…`, `replicate_key_add…`, `update_key_on_another…`, `replicate_key_update…`); селектор `get_vds_instance_keys`; `migrate` → `get_all_active_valid_keys`. Удалить тесты удалённых сервисов.
7. **Миграции** — `RemoveField` `MTPRotoKey.vds`/`node_number`/`tls_domain`, `VDSInstance.user_limit`. Только после того как код перестал ссылаться. До дропа `tls_domain` убедиться, что `settings.TLS_DOMAIN` совпадает с прод-данными.
8. **Документация** — `docs/MODELS.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `BUSINESS.md`, `CLAUDE.md`.

### Зафиксированные решения по умолчанию

- **`KeysLimitReached`** — новое доменное исключение в `apps/vds/exceptions.py` в стиле остальных (docstring = текст пользователю).
- **`TLS_DOMAIN`** — значение взять из текущих прод-данных / `.env` (одинаково на всех VDS).
- **`GLOBAL_KEYS_LIMIT`** — ⚠️ точное число подтвердить у владельца перед Шагом 4.
- Ветку не заводим, работаем в `main`. Коммит — только по явной отмашке владельца.

### Что НЕ входит (отложено в отдельные задачи)

- Периодический страховочный reconcile (через будущий GET-эндпоинт со списком пользователей на стороне VDS + дифф).
- Автодобор существующих ключей на свежедобавленный VDS (`is_healthy=True` сразу, триггера sync нет) — закроется будущим reconcile.

---

## Прогресс реализации (контекст для следующего агента)

**Состояние на 2026-06-14: Шаги 1–5 ВЫПОЛНЕНЫ, тесты зелёные (backend 252 шт., bot 45 шт.). Осталось: Шаги 6–8.**

Работаем в `main`, без коммитов (по явной отмашке владельца). `make test` падает из-за `python` без venv — гонять тесты через `.venv/bin/python manage.py test --settings=config.test_settings`.

### Подтверждённые у владельца значения
- `TLS_DOMAIN = "beatvault.ru"` (default в `config/settings/vds.py`).
- `GLOBAL_KEYS_LIMIT = 1000` (оставлено как боевое значение).

### Что сделано по шагам
- **Шаг 1.** `config/settings/vds.py`: добавлены `TLS_DOMAIN`, `GLOBAL_KEYS_LIMIT`. Тест `apps/vds/tests/test_settings.py`.
- **Шаг 2.** `MTPRotoKey`: `__str__` нейтральный; `get_secret_token()` → `settings.TLS_DOMAIN`; единственный генератор `get_proxy_link(*, server_name)` (старый no-arg удалён, `get_proxy_link_for_server` переименован). Все вызывающие переведены на `get_proxy_link(server_name=...)`.
- **Шаг 3.** Селекторы `count_active_valid_keys()`, `get_healthy_vds_instances()`. Новый инфра-сервис `push_key_to_server_infra_service.py` (идемпотентный POST, 409→skip). Таски `push_key_to_servers_task(key_id)` + `push_key_to_server_task(server_id, username, secret)` в `apps/vds/tasks.py` (ретраи + `_handle_replication_failure`).
- **Шаг 4.** `IssueKeyService` — чистая запись в БД + `push_key_to_servers_task.delay`, проверка `GLOBAL_KEYS_LIMIT` → `KeysLimitReached`, без выбора сервера. `UpdateKeyService` — локальная регенерация `token` + пинок, без HTTP/выбора сервера. Исключение `KeysLimitReached` добавлено.
- **Шаг 5 (контракты/бот).** `IssuedKeyOut`/`UpdateKeyOut` — поле `link` удалено (DTO теперь только `expired_date`). `first_free_link_service`/`get_free_link_via_referrals`/`update_key_service` больше не зовут `get_proxy_link()` и не передают `link`. `broadcast_proxy_links_service` → кнопка `📡 Мои серверы` (`callback_data="my_servers"`). Резолвер `_resolve_active_key_link` удалён, `resolve_context` для не-NONE возвращает `{}` (generic skip-ветка `continue` в `SendMailingService` оставлена для будущих резолверов). Enum `ContextResolverType.ACTIVE_KEY_LINK` удалён; в историческом `0001_initial` ссылка на удалённый член заменена на литерал `1` (choices в миграциях косметические), `0008_alter_mailing_context_resolver` пересобирает choices. **Доп. вне таблицы плана (решение владельца «Перевести на Мои серверы»):** `send_free_link_to_user_task` (admin-экшен) больше не передаёт `link`; шаблон `proxy_link_with_message` переведён на `my_servers`-кнопку дата-миграцией `0009_update_proxy_link_with_message_template` (по прецеденту `0007` для `proxy_purchased`); та же миграция сбрасывает осиротевшие `Mailing.context_resolver=1 → 0`. **Бот (`bot/`, тот же репо):** хендлеры уже использовали только `expired_date`; убрано теперь-неиспользуемое поле `link` из dataclass'ов `FreeTrialKey`/`ReissuedKey`/`ReferralRewardKey` + обновлены бот-тесты (`test_handlers.py`, `domains/*/test_client.py`). Бот-тесты гонять через `bot/.venv/bin/pytest` из каталога `bot/`.

### Принятые решения по реализации (важно для Шагов 5–8)
- **`vds` сделан nullable на Шаге 4** (миграция `apps/vds/migrations/0018_alter_mtprotokey_vds.py`, `AlterField null=True`), чтобы выдача стала чистой записью без NOT NULL-блокера. `RemoveField` для `vds`/`node_number`/`tls_domain` + `VDSInstance.user_limit` — на **Шаге 7** (как в плане). `node_number`/`tls_domain` при `create()` дают `""` — ограничение БД не нарушают.
- **`link` ещё в DTO.** `IssuedKeyOut`/`UpdateKeyOut` пока содержат `link` (убрать на **Шаге 5**). На Шаге 4 транзитивно: `link = key.get_proxy_link(server_name=key.node_number)`, где `node_number=""` — ссылка «битая», но поле сериализуется. На Шаге 5 поле и эти вызовы уходят.
- **Инвариант «одна строка на юзера» сохранён.** `IssueKeyService` перед `create()` делает `get_keys_by_username(username).delete()` (как раньше это делал удаляемый `AddNewKeyInfraService`). В исходном snippet'е спеки удаления не было — владелец попросил вернуть (2026-06-14), чтобы не копить мёртвые строки. `Payment.key` = `OneToOneField(on_delete=SET_NULL)`, поэтому удаление ключа НЕ сносит историю платежей (только отвязывает). `UpdateKeyService` тоже удаляет прочие ключи юзера. Тесты платежей: count == 1.
- **`get_healthy_vds_instances()`** = `active().filter(is_healthy=True)` — добавлен сверх явного списка Шага 3 (нужен для фан-аута пуша).
- **`remove_key_from_servers_task` НЕ делался** — в нумерованных шагах 1–8 его нет; отзыв ключа = существующий дневной `RemoveExpiredKeysDailyService` (без изменений). Если нужен мгновенный remove-пинок — отдельная задача.

### Образовавшийся мёртвый код (удаляется на Шаге 6 — ПРОВЕРИТЬ список плана)
- `AddNewKeyInfraService`, `ReplicateKeyAddToServerInfraService`, `ReplicateKeyUpdateToServerInfraService` + таски `add_key_to_another…`, `replicate_key_add…`, `update_key_on_another…`, `replicate_key_update…` — по плану Шага 6.
- **Не в списке плана, но стало мёртвым после Шага 4:** `UpdateKeyInfraService` (`update_key_infra_service.py`, его тест, реэкспорт в `services/__init__.py`) — больше никем не вызывается; `NoVDSAvailable` — больше не используется сервисами. Решить на Шаге 6, удалять ли заодно (рекомендуется — уточнить у владельца).

### Где смотреть незакрытые хвосты для Шагов 6–8
- **Шаг 6:** удалить мёртвые сервисы/таски/тесты (см. выше); селектор `get_vds_instance_keys` (+ его тест `TestGetVdsInstanceKeys`); `MigrateVdsKeysInfraService` → `get_all_active_valid_keys`.
- **Шаг 7:** `RemoveField` `vds`/`node_number`/`tls_domain`/`user_limit`; убрать `VDSQuerySet.order_by_population`/`get_least_populated`, `VDSInstance.is_available`, селектор `get_least_populated_vds` (+ тесты `TestVDSQuerySet`, `TestGetLeastPopulatedVds`); убрать `vds=`/`node_number`/`tls_domain` из `apps/vds/tests/factories.py` и из всех тестов, что их ещё передают. До дропа `tls_domain` сверить, что прод-значение == `beatvault.ru`.
- **Шаг 8:** `docs/MODELS.md`, `ARCHITECTURE.md`, `CONTRACTS.md`, `BUSINESS.md`, `CLAUDE.md`.
