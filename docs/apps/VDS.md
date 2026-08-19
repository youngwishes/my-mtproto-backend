# VDS

## Зона ответственности

MTProto-ключи, VDS-инстансы и асинхронное выравнивание DB state на fleet.
Инварианты хранения находятся в [MODELS.md](../MODELS.md), HTTP-взаимодействие с
нодами — в [CONTRACTS.md](../CONTRACTS.md), общий поток — в
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Карта компонентов

- Hosting, VDSInstance, MTPRotoKey — доменные модели.
- issue/update services — DB-изменение ключа.
- push/sync/remove infra services — идемпотентная доставка и очистка VDS.
- health-check services — состояние нод и восстановление.
- tasks.py — fan-out, retry, reconcile, cleanup и уведомления.

## Зависимости

Использует core, users и notifications. Payments и users вызывают выдачу или
продление MTProxy-ключа.

## Границы

БД — source of truth; VDS хранит производную копию. Один ключ содержит один
secret для всей fleet. Issue/reissue не выполняет синхронный HTTP, а server
links формируются на лету.
