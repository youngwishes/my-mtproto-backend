# VDS

## Зона ответственности

Управление VDS-серверами (прокси-нодами) и MTProto-ключами пользователей. Взаимодействует с FastAPI-инстансами на каждом VDS через REST API для создания, обновления и удаления ключей.

## Ключевые модели

- **VDSInstance** — прокси-сервер. Хранит IP-адреса, порт, лимит пользователей. Менеджер выбирает наименее нагруженный сервер.
- **MTPRotoKey** — прокси-ключ пользователя. Хранит token, TLS-домен, дату истечения, связь с VDS и пользователем. Формирует `tg://proxy` ссылку.

## Сервисы

- **IssueKeyService** — создаёт ключ на VDS через HTTP-запрос, сохраняет в БД
- **AddNewKeyInfraService** — реплицирует ключ на другие VDS-ноды
- **RemoveKeyInfraService** — удаляет ключ с VDS
- **UpdateKeyService** — перевыпуск ключа (новый token, тот же срок)
- **UpdateKeyInfraService** — обновляет ключ на VDS через HTTP

## Celery-задачи

- **remove_user_keys_daily** — ежедневное удаление истёкших ключей (9:00 UTC)
- **notify_before_removing_daily** — уведомление за 1 день до истечения (15:00 UTC)
- **notify_before_removing_daily_hour_before** — уведомление за 1 час (8:00 UTC)
- **add/remove_key_to_another_vds_instances_task** — репликация ключей между нодами
- **broadcast_proxy_links_task** — массовая рассылка ссылок

## Зависимости

Зависит от: core (декораторы, транспорт), notifications (шаблоны уведомлений), users (модель SystemUser).
От него зависят: payments (выдача ключа при оплате), users (бесплатные ключи).
