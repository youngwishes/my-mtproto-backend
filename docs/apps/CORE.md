# Core

## Зона ответственности

Общие Django-примитивы, базовые модели, исключения, декораторы и Telegram
transport. Архитектурное место приложения описано в
[ARCHITECTURE.md](../ARCHITECTURE.md), общие модели — в
[MODELS.md](../MODELS.md).

## Карта компонентов

- models.py — BaseDjangoModel и active queryset.
- decorators.py — общие инфраструктурные декораторы.
- exceptions.py — базовые service/infra exceptions.
- **dtos.py** — общие transport-neutral DTO.
- telegram/transport.py — низкоуровневая отправка Telegram-сообщений.

## Зависимости

Core не зависит от доменных приложений; остальные Django-приложения используют
его базовые типы и transport.

## Границы

Core не содержит продуктовых правил, orchestration платежей, ключей или
подписок. Доменные исключения и DTO остаются в приложении-владельце.
