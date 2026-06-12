# VDS

## Зона ответственности

Управление VDS-серверами (прокси-нодами) и MTProto-ключами пользователей. Взаимодействует с FastAPI-инстансами на каждом VDS через REST API для создания, обновления и удаления ключей.

## Ключевые модели

- **VDSInstance** — прокси-сервер. Хранит IP-адреса, порт, лимит пользователей, флаг `is_healthy`. Менеджер выбирает наименее нагруженный сервер.
- **MTPRotoKey** — прокси-ключ пользователя. Хранит token, TLS-домен, дату истечения, связь с VDS и пользователем. Формирует `tg://proxy` ссылку.

## Сервисы

- **IssueKeyService** — создаёт ключ на VDS через HTTP-запрос, сохраняет в БД
- **AddNewKeyInfraService** — добавляет ключ на главный VDS, запускает задачи репликации
- **ReplicateKeyAddToServerInfraService** — реплицирует POST-создание ключа на конкретный сервер (409 игнорируется)
- **ReplicateKeyUpdateToServerInfraService** — реплицирует PATCH-обновление ключа на конкретный сервер (404 → fallback POST)
- **VDSHealthCheckInfraService** — проверяет доступность сервера GET-запросом; возвращает True если ответ получен, False если соединение не установлено
- **RemoveKeyInfraService** — удаляет ключ с VDS
- **UpdateKeyService** — перевыпуск ключа (новый token, тот же срок)
- **UpdateKeyInfraService** — обновляет ключ на VDS через HTTP

## Celery-задачи

- **remove_user_keys_daily** — ежедневное удаление истёкших ключей (9:00 UTC)
- **notify_before_removing_daily** — уведомление за 1 день до истечения (15:00 UTC)
- **notify_before_removing_daily_hour_before** — уведомление за 1 час (8:00 UTC)
- **add_key_to_another_vds_instances_task** — диспетчер: создаёт задачу `replicate_key_add_to_server_task` для каждого активного сервера кроме текущего
- **replicate_key_add_to_server_task** — POST-репликация на один сервер; при ошибке: retry с экспоненциальной задержкой (60s → 240s → 960s), при исчерпании ретраев — `_handle_replication_failure`
- **update_key_on_another_vds_instances_task** — диспетчер: создаёт задачу `replicate_key_update_to_server_task` для каждого активного сервера кроме текущего
- **replicate_key_update_to_server_task** — PATCH-репликация на один сервер; тот же механизм retry
- **check_vds_health_task** — каждые 5 минут проверяет нездоровые (`is_healthy=False`) серверы; при восстановлении: выставляет `is_healthy=True`, запускает `sync_keys_to_vds_task`
- **sync_keys_to_vds_task** — синхронизирует все активные ключи БД на конкретный сервер
- **broadcast_proxy_links_task** — массовая рассылка ссылок

## Механизм отказоустойчивости репликации

```
Ошибка репликации
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
  → восстановлен → is_healthy = True, sync_keys_to_vds_task
```

## Зависимости

Зависит от: core (декораторы, транспорт), notifications (шаблоны уведомлений), users (модель SystemUser).
От него зависят: payments (выдача ключа при оплате), users (бесплатные ключи).
