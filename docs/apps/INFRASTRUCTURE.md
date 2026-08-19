# Infrastructure

## Зона ответственности

Учёт проектных серверов и их оплат, admin-интерфейс и напоминание владельцу
проекта. Поля хранения зафиксированы в [MODELS.md](../MODELS.md), место в
системе — в [ARCHITECTURE.md](../ARCHITECTURE.md).

## Карта компонентов

- models.py — ProjectServer и связь с хостингом.
- admin.py — управление серверным инвентарём.
- selectors.py — выбор серверов, требующих напоминания.
- services/project_server_payment_reminder_service.py — формирование и отправка
  ежедневного напоминания.
- tasks.py — Celery entrypoint и wiring сервиса.

## Зависимости

Использует core transport, MY_TELEGRAM_ID и модель хостинга из VDS. Доменные
VDS/VPN-инстансы не читает и не изменяет.

## Границы

Нет автоматической оплаты, валютной арифметики, discovery, provider API,
истории уведомлений или подтверждения доставки.
