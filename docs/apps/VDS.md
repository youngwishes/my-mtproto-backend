# VDS

## Зона ответственности

Управление VDS-серверами (прокси-нодами) и MTProto-ключами пользователей. Взаимодействует с FastAPI-инстансами на каждом VDS через REST API для создания, обновления и удаления ключей.

## Reconcile-модель

БД — единственный источник правды. `MTPRotoKey` — это один секрет, валидный на **всём флоте**, без понятия «домашний сервер». Серверы равноправны (каждый активный ключ присутствует на всех здоровых VDS); присутствие секретов на серверах — производный кэш, выравниваемый reconcile-механизмами (мгновенный пуш при выдаче/перевыпуске + бэкфилл при восстановлении сервера).

## Ключевые модели

- **VDSInstance** — прокси-сервер. Хранит IP-адреса, порт, `is_keys_available`, `is_healthy`, `location`. `name` — DNS-субдомен сервера в хосте proxy-URL (`{name}.beatvault.ru`). Менеджер — `ActiveQuerySet` (`.active()`); выбора «наименее нагруженного» сервера больше нет.
- **MTPRotoKey** — прокси-ключ пользователя: token, дата истечения, связь с пользователем (без `vds`/`node_number`/`tls_domain`). `get_proxy_link(*, server_name)` формирует `tg://proxy` ссылку; домен маскировки — из `settings.TLS_DOMAIN`.

## Сервисы

- **IssueKeyService** — выдача ключа: чистая запись в БД + пинок `push_key_to_servers_task` (без выбора сервера и синхронного HTTP). Глобальный лимит `settings.GLOBAL_KEYS_LIMIT` → `KeysLimitReached`.
- **UpdateKeyService** — перевыпуск ключа (новый token, тот же срок): запись в БД + пинок доставки.
- **PushKeyToServerInfraService** — идемпотентно доставляет один секрет на один здоровый VDS (POST `/api/users`, `409` → skip).
- **SyncKeysToVdsInfraService** — синхронизирует все активные валидные ключи БД на конкретный сервер (бэкфилл при восстановлении).
- **MigrateVdsKeysInfraService** — досылает все активные валидные ключи на остальные активные серверы.
- **GetMyServersService** — генерирует `tg://proxy` ссылки на лету для каждого активного VDS.
- **VDSHealthCheckInfraService** — проверяет доступность сервера GET-запросом.
- **RemoveUserKeyInfraService** / **RemoveKeysFromVdsInstanceInfraService** / **RemoveDeadKeysFromVdsInfraService** — удаление ключей с VDS.
- **RemoveExpiredKeysDailyService** — дневное удаление истёкших ключей.

## Celery-задачи

- **remove_user_keys_daily** — ежедневное удаление истёкших ключей (9:00 UTC)
- **notify_before_removing_daily** — уведомление за 1 день до истечения (15:00 UTC)
- **notify_before_removing_daily_hour_before** — уведомление за 1 час (8:00 UTC)
- **push_key_to_servers_task(key_id)** — мгновенный пинок: фан-аут секрета одного ключа на все здоровые VDS (по `push_key_to_server_task` на каждый)
- **push_key_to_server_task** — идемпотентный POST на один сервер; при ошибке: retry с экспоненциальной задержкой (60s → 240s → 960s), при исчерпании ретраев — `_handle_replication_failure`
- **migrate_vds_keys_task** — досылка всех активных ключей на остальные серверы (админ-экшен)
- **sync_keys_to_vds_task** — синхронизирует все активные ключи БД на конкретный сервер
- **remove_dead_keys_from_vds_task** / **remove_key_from_another_vds_instances_task** — удаление ключей с серверов
- **check_vds_health_task** — каждые 5 минут проверяет нездоровые (`is_healthy=False`) серверы; при восстановлении: выставляет `is_healthy=True`, запускает `sync_keys_to_vds_task`
- **broadcast_proxy_links_task** — массовая рассылка

## Механизм отказоустойчивости доставки

```
Ошибка доставки ключа (push_key_to_server_task)
      │
      ▼
retry (max 3, backoff: 60s → 240s → 960s)
      │ исчерпан
      ▼
_handle_replication_failure
  → VDSInstance.is_healthy = False
  → уведомление администратора в Telegram
      │
      ▼
check_vds_health_task (каждые 5 мин)
  → VDSHealthCheckInfraService: GET internal_url
  → восстановлен → is_healthy = True, sync_keys_to_vds_task (бэкфилл)
```

## Зависимости

Зависит от: core (декораторы, транспорт), notifications (шаблоны уведомлений), users (модель SystemUser).
От него зависят: payments (выдача ключа при оплате), users (бесплатные ключи).
