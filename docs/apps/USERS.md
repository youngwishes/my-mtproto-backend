# Users

## Зона ответственности

Управление пользователями, бесплатными ключами и реферальной программой. Пользователь идентифицируется по Telegram ID, хранящемуся в поле `username` модели `SystemUser`.

## Ключевые модели

- **SystemUser** — расширяет `AbstractUser`. Хранит флаги юридического согласия
  и использования бесплатного периода, Telegram-username и данные о реферале.

## Сервисы

- **CheckFirstFreeLinkService** — проверяет доступность бесплатного периода и определяет его длительность (MONTH / TWO_WEEK / WEEK / NOT_AVAILABLE)
- **GetLegalConsentStatusService** — read-only проверяет сохранённое согласие
- **AcceptLegalConsentService** — создаёт пользователя только после согласия
- **FirstFreeLinkService** — выдаёт бесплатный ключ новому пользователю
- **ReferralCabinetService** — статистика реферальной программы
- **GetFreeLinkViaReferralsService** — выдаёт бесплатный ключ за 5+ активных рефералов

## Celery-задачи

- **send_invite_to_chat_task** — рассылка приглашений на Telegram-канал
- **send_free_link_to_user_task** — отправка бесплатных ссылок пользователям

## Зависимости

Зависит от: core (исключения, декораторы), vds (выдача ключей).
От него зависят: payments (поиск пользователя по username).
