# Notifications

## Зона ответственности

Хранение шаблонов, единичные уведомления и массовые рассылки. Структура моделей
описана в [MODELS.md](../MODELS.md), взаимодействия компонентов — в
[ARCHITECTURE.md](../ARCHITECTURE.md).

## Карта компонентов

- NotificationTemplate, Mailing — шаблоны и состояние рассылок.
- SendNotificationService, SendMailingService — доменная отправка.
- selectors.py — выбор шаблонов, рассылок и получателей.
- resolvers.py — построение разрешённого контекста шаблона.

## Зависимости

Использует core transport, users и селекторы VDS. Уведомления вызываются из VDS,
payments и infrastructure.

## Границы

Приложение не владеет бизнес-событиями вызывающих доменов. Кнопка шаблона может
содержать URL или callback; обработчик callback принадлежит боту.
