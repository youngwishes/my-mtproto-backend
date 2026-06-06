# Core

## Зона ответственности

Инфраструктурное ядро проекта. Предоставляет базовые модели, исключения, декораторы и транспортный слой для отправки сообщений в Telegram. Не содержит бизнес-логики.

## Ключевые модули

- **models.py** — `BaseDjangoModel` (is_active, created_at, updated_at) и `BaseServiceDTO` для передачи данных между слоями
- **exceptions.py** — `BaseError`, `BaseServiceError`, `BaseInfraError` — базовые классы исключений для всех приложений
- **decorators.py** — `@log_service_error`, `@log_infra_error` — обёртки для `__call__` сервисов, логирующие ошибки в Telegram
- **protocols.py** — `IService` — протокол, описывающий контракт сервиса
- **handle_error.py** — DRF exception handler, преобразующий `BaseServiceError` в HTTP-ответ
- **telegram/transport.py** — `send_telegram_message()`, `is_channel_member()` — отправка сообщений через pyTelegramBotAPI с lazy-инициализацией бота
- **telegram/error_logger.py** — форматирование и отправка ошибок администратору

## Зависимости

Зависит от: Django, pyTelegramBotAPI.
От него зависят: все остальные приложения (модели, исключения, декораторы, транспорт).
