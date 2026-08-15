# Infrastructure

## Зона ответственности

`apps.infrastructure` хранит независимый реестр оплат всех проектных серверов и
отправляет администратору одно ежедневное Telegram-напоминание по активным
записям, срок оплаты которых наступит завтра, наступил сегодня или уже прошёл.
Реестр создаётся, редактируется и деактивируется только вручную через Django
Admin.

## Модель и Admin

`ProjectServer` хранит уникальный IPv4, обязательный `Hosting`, положительную
месячную цену, валюту `USDT`/`RUB`/`EUR`/`USD`, следующую дату оплаты и краткое
назначение. Связь с `Hosting` защищена через `PROTECT`. Admin показывает все эти
поля, позволяет искать, фильтровать и редактировать платёжные значения и
active-state; публичного API, web UI и bot-меню у приложения нет.

## Модули и поток напоминания

- `models.py`, `enums.py`, `admin.py` владеют реестром и его Admin-представлением.
- `selectors.py` возвращает активные записи с `next_payment_date <= tomorrow`,
  подгружает `Hosting` и сортирует по дате и IPv4.
- `services/project_server_payment_reminder_service.py` получает selector,
  Telegram sender, ID администратора и timeout через DI. Он материализует
  выборку один раз и отправляет не больше одного HTML-safe сообщения со статусом,
  IPv4, хостингом, ценой и валютой, датой и назначением каждой записи.
- `tasks.py` содержит bound Celery task, который использует локальную дату и при
  любой ошибке делает до трёх повторов с задержкой 30 секунд.
- Celery Beat ежедневно в 11:00 UTC запускает
  `apps.infrastructure.tasks.send_project_server_payment_reminder_task`.

Полный поток:

`Beat → task → factory → selector → ProjectServer + Hosting → service → Telegram → MY_TELEGRAM_ID`.

Выполнение read-only: даты оплаты и active-state автоматически не меняются,
поэтому просроченная активная запись повторяется каждый день до ручного
исправления или деактивации.

## Зависимости

- `apps.core`: `BaseDjangoModel` и существующий Telegram transport;
- `apps.vds`: только справочник `Hosting`;
- Django ORM/Admin, Celery и настройки `MY_TELEGRAM_ID`/`TELEGRAM_TIMEOUT`.

Другие приложения не импортируют `apps.infrastructure`; приложение не читает и
не изменяет `VDSInstance` или `VPNInstance`.

## Границы

Нет discovery, синхронизации или backfill; автоматической оплаты или переноса
даты; конвертации валют и итогов; шаблонов, истории или подтверждения доставки;
pagination/truncation; новых получателей; отдельного логирования инвентаря или
Telegram-данных. Напоминание не добавляет API/provider contract и не изменяет
операционные VDS/VPN-потоки.
