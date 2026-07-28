# Явное согласие при первом запуске бота — план реализации

**Статус:** approved
**Business:** `docs/features/legal-consent/business.md` (`approved`)
**Архитектура:** утверждены отдельные `POST /users/consent/status/`
(read-only) и `POST /users/consent/accept/` (atomic/idempotent);
поле `SystemUser.legal_terms_accepted` по умолчанию равно `false`, существующим
строкам миграция выставляет `true`; `check-first-free-link` для отсутствующего
пользователя или `legal_terms_accepted=false` без записи поднимает
`LegalTermsNotAccepted`; бот показывает consent-экран, переносит допустимый
referral в callback и после accept редактирует то же сообщение.

Точные wire-контракты:

- status request: `{"username": "<numeric Telegram ID>"}`;
- status response: `{"legal_terms_accepted": false|true}`, причём отсутствующий
  пользователь даёт `false` и операция строго не пишет в БД;
- accept request: обязательный `username` как numeric string, опциональные
  `telegram_username` и numeric-string `invited_from_username`;
- accept response: `{"legal_terms_accepted": true}`;
- нечисловой либо self-referrer отклоняется backend с HTTP 400; бот такие
  значения не отправляет.

## Порядок и партии

Пункты выполняются последовательно: партия 1 — `LC-01`, затем партия 2 —
`LC-02`. Bot-клиент и обработчик из `LC-02` зависят от контрактов backend из
`LC-01`; параллельная реализация небезопасна. Каждый implementer владеет только
файлами своего пункта и не меняет файлы второй партии.

### LC-01 — Backend: хранение согласия и раздельные status/accept операции

- **Результат:** `SystemUser` получает boolean-поле
  `legal_terms_accepted` с default `false`; data migration атомарно сохраняет
  всем существующим пользователям `true`; status принимает numeric-string
  `username` и строго read-only возвращает сохранённое значение либо `false`
  для отсутствующего пользователя; accept принимает утверждённый request,
  атомарно и идемпотентно создаёт согласившегося пользователя или переводит
  существующего `false → true`, всегда возвращая
  `{"legal_terms_accepted": true}` и не перезаписывая referrer.
  `check-first-free-link` для отсутствующего пользователя либо
  `legal_terms_accepted=false` поднимает доменный
  `LegalTermsNotAccepted`, который существующий API error handler отображает
  в HTTP 400, и не выполняет write.
- **Связанные требования:** BR-001–BR-003, BR-006–BR-007, BR-009–BR-012;
  AC-001, AC-004–AC-010, AC-012–AC-013.
- **Зависимости:** нет; это первая партия.
- **Файлы и граница владения:**
  - изменить `src/apps/users/models.py`, `src/apps/users/selectors.py`,
    `src/apps/users/exceptions.py`,
    `src/apps/users/services/check_first_free_link_service.py`,
    `src/apps/users/services/__init__.py`,
    `src/apps/users/api/v1/urls.py`,
    `src/apps/users/api/v1/views/__init__.py`;
  - создать сфокусированные DTO/сервисы/views/serializers для consent рядом с
    существующими модулями в
    `src/apps/users/services/dtos/`, `src/apps/users/services/` и
    `src/apps/users/api/v1/{serializers,views}/`, с явными re-export;
  - создать следующую миграцию после
    `src/apps/users/migrations/0016_normalize_none_usernames.py`;
  - создать/изменить только профильные тесты
    `src/apps/users/tests/test_consent_migration.py`,
    `src/apps/users/tests/test_consent_status_view.py`,
    `src/apps/users/tests/test_consent_accept_view.py` и
    `src/apps/users/tests/test_check_first_free_link.py`;
  - обновить backend-разделы `docs/CONTRACTS.md`, `docs/MODELS.md`,
    `docs/BUSINESS.md` и `docs/apps/USERS.md`.
- **RED:** сначала зафиксировать тестами точные JSON-контракты status/accept;
  status для отсутствующего numeric-string `username` возвращает
  `{"legal_terms_accepted": false}` и не пишет в БД; status возвращает
  сохранённый флаг; accept создаёт ровно одну запись с
  `legal_terms_accepted=true`; валидный `invited_from_username` сохраняется
  только при accept; нечисловой либо self-referrer возвращает HTTP 400;
  повторный accept не создаёт дубль и не меняет referrer; два конкурентных
  accept для одного Telegram ID оставляют ровно одну запись и оба завершаются
  согласованным успешным результатом; accept для существующего пользователя с
  `legal_terms_accepted=false` переводит флаг в `true`, не перезаписывая его
  referrer; ошибка внутри accept откатывает всю новую запись; миграция сохраняет
  число/данные пользователей и выставляет флаг `true`; новый model instance без
  accept имеет `false`; `check-first-free-link` для отсутствующего пользователя
  и для пользователя с `legal_terms_accepted=false` поднимает
  `LegalTermsNotAccepted`, через существующий handler возвращает HTTP 400 и не
  делает write.
  Команда RED:
  `make test ARGS="apps.users.tests.test_consent_migration apps.users.tests.test_consent_status_view apps.users.tests.test_consent_accept_view apps.users.tests.test_check_first_free_link"`;
  ожидается падение по отсутствующему полю, endpoints и изменённой семантике
  check-first-free-link.
- **Минимальное production-изменение (GREEN):** добавить поле и schema+data
  migration; переиспользовать/добавить selector для read-only lookup; реализовать
  сервисы как `@final` frozen dataclass с keyword-only `__call__`, DTO и
  module-level wiring; serializers должны валидировать `username` и
  `invited_from_username` как numeric strings и отклонять invalid/self-referrer
  HTTP 400; accept обернуть в одну DB-транзакцию и корректно обработать
  конкурентное создание с существующей уникальностью Telegram ID; для
  существующего пользователя обновлять только `legal_terms_accepted`, не
  referrer; зарегистрировать два POST endpoint с `Bot-Auth-Token`; добавить
  `LegalTermsNotAccepted` по действующему паттерну доменных исключений и заменить
  write-путь `check-first-free-link` на проверку согласия, не меняя правила
  бесплатного периода.
- **Документация:** описать новое поле и backfill, request/response/error
  contracts обоих endpoint, HTTP 400 для invalid/self-referrer,
  read-only/atomic/idempotent семантику и `LegalTermsNotAccepted`; явно отметить,
  что прежний endpoint больше не регистрирует пользователя.
- **GREEN-команда:**
  `make test ARGS="apps.users.tests.test_consent_migration apps.users.tests.test_consent_status_view apps.users.tests.test_consent_accept_view apps.users.tests.test_check_first_free_link"`.
- **Критерий завершения:** GREEN-команда проходит; тесты доказывают отсутствие
  write до accept, полный rollback при ошибке, ровно одного пользователя после
  повторного и конкурентного accept, `false → true` без перезаписи referrer,
  HTTP 400 для invalid/self-referrer, `LegalTermsNotAccepted` без write и
  корректный migration backfill; контракты и model docs совпадают с кодом.

### LC-02 — Bot: consent-экран, referral callback и редактирование сообщения

- **Результат:** `/start` сначала вызывает status; новый пользователь видит
  одно сообщение с `/terms`, `/privacy` и одной accept-кнопкой без главного
  меню; допустимый referral переносится только в callback
  `accept_legal_terms:<referrer>`, а без него используется
  `accept_legal_terms`; accept-handler вызывает backend accept по точному
  wire-контракту и редактирует исходное сообщение в прежний стартовый экран с
  главным меню; ошибки не открывают меню, повторный запуск безопасен.
- **Связанные требования:** BR-001–BR-006, BR-008, BR-011–BR-013;
  AC-001–AC-009, AC-011–AC-013.
- **Зависимости:** `LC-01` завершён и его endpoint contracts зафиксированы.
- **Файлы и граница владения:** обязательно создать
  `bot/src/domains/consent/client.py`,
  `bot/src/domains/consent/__init__.py`,
  `bot/tests/domains/consent/test_client.py` и соответствующий test-package
  `__init__.py`; изменить `bot/src/dependencies.py`,
  `bot/src/handlers/start.py`, `bot/src/handlers/__init__.py`,
  `bot/src/keyboards.py`, `bot/src/messages.py`,
  `bot/tests/test_dependencies.py`, `bot/tests/test_handlers.py`;
  `bot/src/core/backend_client.py` и
  `bot/tests/core/test_backend_client.py` менять только если существующий
  generic HTTP transport объективно не позволяет consent domain-client
  отправить утверждённые POST-запросы; обновить `bot/README.md`.
  Backend и миграционные файлы из `LC-01` этой партии не принадлежат.
- **RED:** сначала зафиксировать тестами: status вызывается до прежнего
  onboarding; consent domain-client отправляет status request
  `{"username": "<numeric>"}`, разбирает
  `{"legal_terms_accepted": false|true}`, отправляет accept request только с
  `username`, опциональным `telegram_username` и валидным numeric-string
  `invited_from_username`, разбирает `{"legal_terms_accepted": true}`; для
  нового пользователя отправляется ровно один consent-экран с двумя заданными
  URL и одной кнопкой без меню; без referral callback data строго равно
  `accept_legal_terms`, с referral —
  `accept_legal_terms:<referrer>`; максимальный вариант равен 39 байтам и тестом
  подтверждён как `<=64` байт; referral не отправляется backend до accept;
  сохранённое `legal_terms_accepted=true` ведёт в прежний start flow; callback
  вызывает accept с Telegram-данными и допустимым referral, затем редактирует то
  же сообщение; invalid/self-referrer не передаётся; повторный callback
  безопасно показывает start; ошибки status/accept не показывают меню; ошибка
  edit после успешного accept не отменяет backend результат, а следующий
  `/start` показывает обычный экран.
  Команда RED:
  `cd bot && uv run pytest tests/test_handlers.py tests/test_dependencies.py tests/domains/consent/test_client.py -q`;
  ожидается падение по отсутствующему consent domain-client, wiring, callback и
  consent UI.
- **Минимальное production-изменение (GREEN):** создать обязательный
  `domains.consent` client с типизированными status/accept вызовами поверх
  существующего generic transport и подключить его через dependency wiring;
  добавить недвусмысленный текст, inline keyboard с двумя URL и одним callback
  точного формата `accept_legal_terms[:<referrer>]`; изменить `/start` на
  status-first branching без прежнего регистрирующего вызова; переносить только
  numeric non-self referrer, сохраняя callback в лимите Telegram 64 bytes;
  добавить aiogram callback handler, который после успешного accept
  переиспользует существующее построение стартового экрана и редактирует
  исходное сообщение; существующую обработку ошибок сохранить без ложного
  перехода в меню.
- **Документация:** в `bot/README.md` описать новый `/start`/accept flow,
  callback, referral propagation и retry-поведение.
- **GREEN-команда:**
  `cd bot && uv run pytest tests/test_handlers.py tests/test_dependencies.py tests/domains/consent/test_client.py -q`.
- **Критерий завершения:** GREEN-команда проходит и тесты однозначно
  подтверждают один consent-экран, отсутствие меню/write до accept, перенос
  валидного referral, точные request/response contracts, callback формата
  `accept_legal_terms[:<referrer>]` длиной не более 64 байт, отсутствие отправки
  invalid/self-referrer, edit того же сообщения, безопасные retry и неизменность
  сохранённого consent при Telegram edit error.

## Финальная проверка после обеих партий

Выполнить последовательно:

1. `make test`
2. `cd bot && uv run pytest -q`
3. `docker compose -f docker-compose.local.yml config --quiet`
4. Проверить согласованность `docs/features/legal-consent/business.md`,
   `docs/CONTRACTS.md`, `docs/MODELS.md`, `docs/BUSINESS.md`,
   `docs/apps/USERS.md` и `bot/README.md`.

План готов к архитектурному ревью, когда в нём нет требований вне approved
business/architecture, обе партии имеют независимые RED/GREEN-критерии,
`LC-02` явно зависит от `LC-01`, а final gate включает полный backend suite,
полный bot suite, валидацию Compose и документацию.
