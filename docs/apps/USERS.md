# Users

## Зона ответственности

Управление пользователями, бесплатными ключами и реферальной программой. Пользователь идентифицируется по Telegram ID, хранящемуся в поле `username` модели `SystemUser`.

## Ключевые модели

- **SystemUser** — расширяет `AbstractUser`. Хранит флаг принятия юридических
  условий (`legal_terms_accepted`, default `false`), флаг использования
  бесплатного периода, Telegram-username, данные о реферале и счётчик
  реферальных ссылок. Миграция поля атомарно выставляет `true` существующим
  пользователям.

## Сервисы

- **GetLegalConsentStatusService** — read-only возвращает сохранённый consent
  либо `false` для отсутствующего пользователя
- **AcceptLegalConsentService** — атомарно и идемпотентно создаёт согласившегося
  пользователя или обновляет только consent существующего, не меняя referrer
- **CheckFirstFreeLinkService** — read-only проверяет доступность бесплатного
  периода согласившегося пользователя и определяет его длительность
  (MONTH / TWO_WEEK / WEEK / NOT_AVAILABLE); для отсутствующего пользователя
  или `legal_terms_accepted=false` поднимает `LegalTermsNotAccepted`
- **FirstFreeLinkService** — выдаёт бесплатный ключ новому пользователю
- **ReferralCabinetService** — статистика реферальной программы
- **GetFreeLinkViaReferralsService** — выдаёт бесплатный ключ за 5+ активных рефералов

## Celery-задачи

- **send_invite_to_chat_task** — рассылка приглашений на Telegram-канал
- **send_free_link_to_user_task** — отправка бесплатных ссылок пользователям

## Зависимости

Зависит от: core (исключения, декораторы), vds (выдача ключей).
От него зависят: payments (поиск пользователя по username).
