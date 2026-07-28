# Явное согласие при первом запуске бота — продуктовая приёмка

**Статус:** approved
**Продуктовый вердикт:** accepted
**Дата приёмки:** 2026-07-28

## Основание

Проверены:

- approved `docs/features/legal-consent/business.md`;
- approved `docs/features/legal-consent/plan.md`, включая зафиксированные в нём
  архитектурные решения (отдельного `architecture.md` у фичи нет);
- полный релевантный diff backend, bot, миграции, тестов и документации;
- положительные batch-review backend и bot, переданные оркестратором;
- свежие результаты финальных gates, переданные оркестратором:
  `make test` — 309 OK; полный bot suite — 93 passed; bot Ruff — clean;
  `makemigrations --check` — no drift; Django check — clean; production и local
  Compose config — clean; diff check — clean.

Дополнительно 2026-07-28 обе утверждённые внешние ссылки были проверены
read-only HTTP-запросом: `https://mtprotokeys.ru/terms` и
`https://mtprotokeys.ru/privacy` вернули HTTP 200.

## Трассировка бизнес-требований

| Требование | Реализующий код или контракт | Подтверждающий тест | Наблюдаемый результат | Статус |
|---|---|---|---|---|
| BR-001 | `bot/src/messages.py::LEGAL_CONSENT_TEXT`, `bot/src/keyboards.py::legal_consent`, поле `SystemUser.legal_terms_accepted` | `test_cmd_start_shows_one_consent_message_without_menu_for_new_user`, `test_creates_exactly_one_accepted_user` | Один экран и одна кнопка недвусмысленно подтверждают оба документа одним boolean-флагом | passed |
| BR-002 | `POST /api/v1/users/consent/status/`, `GetLegalConsentStatusService`, `get_user_by_username` | `test_missing_user_returns_false_without_database_write`, `test_returns_saved_status_without_updating_user` | Status выполняет только SELECT и не создаёт/не обновляет пользователя | passed |
| BR-003 | `ConsentClient.get_status`, ранний return в `cmd_start` до `_render_start_screen` | `test_get_status_sends_only_telegram_id_and_parses_response`, `test_cmd_start_shows_one_consent_message_without_menu_for_new_user` | До accept backend получает только Telegram ID для read-only проверки; `SystemUser` отсутствует | passed |
| BR-004 | `LEGAL_CONSENT_TEXT`, `TERMS_URL`, `PRIVACY_URL`, `legal_consent()` | `test_cmd_start_shows_one_consent_message_without_menu_for_new_user`; HTTP 200 обеих ссылок | Отправляется одно сообщение с двумя рабочими HTML-ссылками и одной утвердительной callback-кнопкой | passed |
| BR-005 | Ветка `not consent_status.legal_terms_accepted` в `cmd_start` | `test_cmd_start_shows_one_consent_message_without_menu_for_new_user`, `test_cmd_start_status_error_does_not_show_menu` | До успешного accept не вызывается free-trial flow и не строится главное меню | passed |
| BR-006 | `_start_referrer`, `_callback_referrer`, callback `accept_legal_terms[:<referrer>]`, backend serializer validation | `test_cmd_start_carries_numeric_referrer_in_bounded_callback`, `test_cmd_start_does_not_carry_invalid_or_self_referrer`, `test_rejects_non_numeric_referrer`, `test_rejects_self_referrer` | Валидный referral живёт только в callback до accept; invalid/self-referral не передаётся и не сохраняется | passed |
| BR-007 | `SystemUser.legal_terms_accepted` с default/db_default `false`; `AcceptLegalConsentService` и `accept_legal_terms` | `test_new_user_defaults_to_not_accepted`, `test_creates_exactly_one_accepted_user` | Обычная новая запись имеет `false`, accept создаёт ровно одного пользователя с `true` | passed |
| BR-008 | `process_legal_consent` переиспользует `_render_start_screen` и вызывает `callback.message.edit_text` | `test_accept_uses_clicking_user_and_edits_same_message_to_start`, существующие start-screen тесты MONTH/NOT_AVAILABLE | То же consent-сообщение заменяется актуальным стартовым экраном с корректным предложением и главным меню | passed |
| BR-009 | Атомарная миграция `0017_systemuser_legal_terms_accepted` | `test_backfill_and_old_code_insert_after_schema_migration`, accepted-ветка start-тестов | Существующие строки сохраняются с прежними данными и получают `true`, поэтому consent-экран им не показывается | passed |
| BR-010 | Раздельные `consent/status/` и `consent/accept/`; read-only status и transactional accept | `test_consent_status_view`, `test_consent_accept_view`, `test_two_concurrent_accepts_create_one_consistently_accepted_user` | Проверка не меняет состояние, принятие атомарно и идемпотентно фиксирует его | passed |
| BR-011 | `update_or_create` обновляет существующему пользователю только consent; bot повторно обрабатывает callback | `test_repeated_accept_does_not_duplicate_user_or_change_referrer`, `test_existing_unaccepted_user_becomes_accepted_without_referrer_change`, `test_repeated_accept_safely_renders_start_each_time` | Повтор не создаёт дубль и не меняет первоначальные Telegram username/referrer | passed |
| BR-012 | Transaction в `AcceptLegalConsentService`; menu строится только после валидного `true` | `test_failure_inside_accept_rolls_back_new_user`, `test_accept_error_does_not_render_start_menu`, `test_accept_invalid_response_does_not_render_or_edit_start_menu`, `test_cmd_start_status_error_does_not_show_menu` | Ошибки status/accept не открывают onboarding; неуспешный accept не оставляет частичную запись, исходное действие можно повторить | passed |
| BR-013 | Сначала сохраняется backend consent, затем выполняется Telegram edit; следующий `/start` читает status | `test_edit_error_after_accept_does_not_require_consent_on_next_start` | Ошибка edit не отменяет сохранённое согласие, следующий `/start` открывает обычный экран | passed |

## Матрица критериев приёмки

| AC | Требование и evidence | Подтверждающий тест/проверка | Наблюдаемый результат | Статус |
|---|---|---|---|---|
| AC-001 | `cmd_start` сначала вызывает status; `GetLegalConsentStatusService` использует read-only selector | `test_missing_user_returns_false_without_database_write`; `test_cmd_start_shows_one_consent_message_without_menu_for_new_user` | Для отсутствующего Telegram ID нет INSERT/UPDATE/DELETE и запись пользователя не появляется | passed |
| AC-002 | `LEGAL_CONSENT_TEXT` содержит `TERMS_URL` и `PRIVACY_URL`; keyboard содержит только accept | `test_cmd_start_shows_one_consent_message_without_menu_for_new_user`; обе ссылки вернули HTTP 200 | Новый пользователь получает одно сообщение, две рабочие ссылки и одну явную кнопку принятия | passed |
| AC-003 | Consent-ветка возвращает управление до `_render_start_screen` | `test_cmd_start_shows_one_consent_message_without_menu_for_new_user`; `test_missing_user_returns_false_without_database_write` | Главное меню отсутствует, free-trial check не вызывается, `SystemUser` отсутствует | passed |
| AC-004 | `AcceptLegalConsentService` создаёт accepted user; `process_legal_consent` редактирует исходное сообщение | `test_creates_exactly_one_accepted_user`; `test_accept_uses_clicking_user_and_edits_same_message_to_start` | После accept существует ровно один `SystemUser(true)`, а то же сообщение содержит обычное меню | passed |
| AC-005 | `_start_referrer` переносит referral в callback; `ConsentClient.accept` отправляет его только при нажатии | `test_cmd_start_carries_numeric_referrer_in_bounded_callback`; `test_accept_uses_clicking_user_and_edits_same_message_to_start`; `test_saves_valid_referrer_only_during_accept` | До accept server-side записи нет, при успешном accept валидный referrer сохраняется | passed |
| AC-006 | Bot нормализует numeric non-self referral, backend повторно валидирует wire-contract | `test_cmd_start_does_not_carry_invalid_or_self_referrer`; `test_accept_does_not_send_invalid_or_self_referrer`; `test_rejects_non_numeric_referrer`; `test_rejects_self_referrer` | Нечисловой и self-referrer не сохраняются; прямой неверный backend-запрос получает HTTP 400 без записи | passed |
| AC-007 | Идемпотентный `update_or_create`, обновляющий только consent существующей записи | `test_repeated_accept_does_not_duplicate_user_or_change_referrer`; `test_repeated_accept_safely_renders_start_each_time`; concurrent accept test | Повторный/конкурентный accept успешен, оставляет одну запись и первоначальный referrer | passed |
| AC-008 | Status path не содержит write; при исключении bot не переходит к start rendering | `test_cmd_start_status_error_does_not_show_menu`; read-only query assertions в `test_consent_status_view` | Ошибка проверки не создаёт пользователя и не показывает главное меню | passed |
| AC-009 | Accept обёрнут в `transaction.atomic`; start rendering идёт только после точного boolean `true` | `test_failure_inside_accept_rolls_back_new_user`; `test_accept_error_does_not_render_start_menu`; `test_accept_invalid_response_does_not_render_or_edit_start_menu`; успешные create/repeat tests | Ошибка не оставляет пользователя и не показывает успешный экран; последующий корректный вызов может завершить регистрацию | passed |
| AC-010 | Миграция добавляет default/db_default `false`, затем одним atomic data migration выставляет существующим строкам `true` | `test_backfill_and_old_code_insert_after_schema_migration`; `makemigrations --check` no drift | Количество, PK и проверенные бизнес-поля существующих пользователей сохранены; их новый флаг равен `true` | passed |
| AC-011 | Миграция даёт существующим пользователям `true`; accepted-ветка `cmd_start` сразу вызывает прежний `_render_start_screen` | migration transition test; `test_cmd_start_checks_consent_before_existing_onboarding`; существующие start-screen tests | Существующий пользователь не видит consent и получает прежний start flow | passed |
| AC-012 | До accept отсутствует `SystemUser`; free-trial path не вызывается. Кандидаты выдачи, рассылок и referral counts строятся из `SystemUser` querysets | `test_missing_user_returns_false_without_database_write`; `test_cmd_start_shows_one_consent_message_without_menu_for_new_user`; полный backend suite 309 OK | До принятия пользователь не может попасть в выборки выдачи/рассылки/реферальной статистики, потому что строки-источника нет | passed |
| AC-013 | Backend consent фиксируется до Telegram edit; новый `/start` снова читает сохранённый status | `test_edit_error_after_accept_does_not_require_consent_on_next_start` | После ошибки edit согласие остаётся `true`, а следующий `/start` показывает обычный экран | passed |

## Пользовательская ценность и границы

Ожидаемая ценность достигнута: новый пользователь явно принимает оба документа
до регистрации и доступа к меню, а существующие пользователи сохраняют прежний
сценарий. Реферальная атрибуция переносится без преждевременной server-side
записи и фиксируется только при успешном accept.

Non-goals соблюдены: тексты и URL самих юридических документов не изменялись;
не добавлены версии/время/отзыв согласия, отдельные согласия, web UI либо новые
правила бесплатного периода, оплаты, рассылок и реферальной программы.
Отклонений от исходной продуктовой цели не обнаружено.

## Failed и unverified

Failed или unverified критериев нет.

## Остаточные риски

- Проверка bot UX выполнена автоматизированными handler/client-тестами с
  aiogram-fakes и HTTP mocks; ручной end-to-end прогон в реальном Telegram перед
  этой приёмкой не выполнялся. Это не блокирует приёмку при зелёном полном bot
  suite.
- Доступность внешних юридических страниц зависит от сайта: на дату приёмки обе
  страницы отвечали HTTP 200, но их последующая доступность и юридическая
  редакция находятся вне scope фичи.
- Миграция, rollback и конкурирующие accept покрыты автоматическими тестами на
  используемой проектом SQLite-конфигурации; фактическое применение миграции в
  production остаётся отдельным release/deploy gate и не выполнялось в рамках
  продуктовой приёмки.

## Итог

Фича принята по продукту. Все BR-001–BR-013 и AC-001–AC-013 имеют
подтверждающие контракты, реализацию и тестовые/наблюдаемые результаты со
статусом `passed`; изменений перед публикацией Pull Request по результатам
приёмки не требуется.
