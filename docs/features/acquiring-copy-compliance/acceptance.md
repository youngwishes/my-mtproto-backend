# Product Acceptance — Acquiring Copy Compliance

- **Verdict:** accepted
- **scope_revision:** 2 (immutable)
- **Reviewed plan items:** ACC-001, ACC-002
- **Reviewed requirements:** BR-001–BR-006, AC-001–AC-005
- **Re-acceptance packet:** ACC-B1-F3
- **Acceptance date:** 2026-08-04

## Основание окончательной приёмки

Проверены approved `business.md`, approved `plan.md`, Scope Contract и task
packet `ACC-B1` revision 2, полный текущий рабочий diff, production-copy,
регрессионные тесты и переданные результаты TDD/batch reviews. Отдельного
`architecture.md` у фичи нет: approved plan фиксирует, что архитектурное
изменение не требуется, поскольку API, модели и взаимодействия компонентов не
меняются.

История повторной приёмки:

- `ACC-B1-F2` исправил три support error, которые после замены contact всё ещё
  описывали обращение через сообщения канала: `VPNSubscriptionDoesNotExist`,
  `AlreadyUsedFree` и `KeyDoesNotExist`. Теперь они используют формулировку
  `напишите в поддержку: @mtprotokeys_support` без channel-oriented wording.
- `ACC-B1-F3` добавил пропущенную финальную точку в approved FAQ-ответ и в его
  exact regression assertion. Иных production/test изменений относительно F2
  packet не передано.

Текущий FAQ посимвольно содержит утверждённый ответ, включая финальную точку:
`Прокси помогает Telegram работать стабильнее и уменьшает потери при плохом интернете, защищает трафик. Максимальная скорость зависит от твоего интернета.`
Сохранённый `⚡️` не меняет смысл. Запрещённый контекст отсутствует.

Definitive read-only batch review текущего tracked diff с SHA-256
`605820832b8bf0a55c3fcd6ea06555491e7a025424b29103e53b50e571c4aa51`
передан с вердиктом **approved**, findings отсутствуют. Reviewer выполнил свежий
F3 targeted test: 1 passed. Этот технический verdict является дополнительным
evidence, но не заменяет продуктовую трассировку ниже.

## Фактические проверки

| Проверка | Наблюдаемый результат | Статус |
|---|---|---|
| F3 TDD evidence из task handoff | Exact FAQ test: 1 failed → 1 passed. RED фиксировал отсутствие финальной точки, GREEN — полный approved FAQ с точкой. | passed |
| Свежий definitive-review запуск F3 `test_info_answers_callback` | Текущий F3 snapshot: 1 passed; exact assertion включает финальную точку. | passed |
| Definitive read-only batch review tracked diff SHA-256 `605820832b8b…` | Verdict `approved`; findings отсутствуют. | passed |
| Финальный read-only F2 batch review snapshot `108e1c…` | F2 baseline verdict `approved`, findings отсутствовали; reviewer подтвердил bot handlers 52/52, targeted backend 9/9, migration pair 2/2 и чистый diff check. Snapshot заменён F3 review и не выдаётся за текущий. | passed |
| F2 TDD evidence из task handoff | Bot: 1 failed → 1 passed; backend: 2 failed / 1 passed → 3 OK. RED фиксировал прежнюю channel-oriented формулировку, GREEN — точный support-copy. | passed |
| `(cd bot && uv run pytest tests/test_handlers.py -q)` после F2 | F2 baseline: 52 passed. | passed |
| `make test ARGS="apps.notifications.tests.test_broadcast_proxy_links_service apps.notifications.tests.test_sorry_server_error_support_migration apps.users.tests.test_exceptions apps.vds.tests.test_exceptions"` после F2 | F2 baseline: 9 tests, `OK`; system check без замечаний. | passed |
| `make test ARGS="apps.notifications.tests.test_crypto_purchase_templates_migration apps.notifications.tests.test_sorry_server_error_support_migration"` после F2 | F2 baseline migration pair: 2 tests, `OK`; system check без замечаний. | passed |
| `(cd bot && uv run pytest -q)` после F2 | F2 root integration baseline: 95 passed. Это не финальный F3 root run. | passed |
| Полный `make test` после F2 | F2 root integration baseline: 470 tests, `OK`; system check без замечаний. Это не финальный F3 root run. | passed |
| `docker compose -f docker-compose.yml config --quiet` после F2 | F2 baseline: exit code 0. Это не финальная F3 validation. | passed |
| `(cd bot && uv run pytest -q)` на финальном F3 snapshot | Свежий root integration run: 95 passed. | passed |
| Полный `make test` на финальном F3 snapshot | Свежий root integration run: 470 tests, `OK`; system check без замечаний. | passed |
| `docker compose -f docker-compose.yml config --quiet` на финальном F3 snapshot | Exit code 0. | passed |
| Ручная проверка текущего FAQ | Production string и exact test совпадают с approved FAQ, включая точку после `интернета.`; `обходит ограничения` и `блокировок` отсутствуют. | passed |
| Ручная проверка текущего runtime support-copy | Все назначенные support call sites используют `@mtprotokeys_support`; F2 wording в трёх errors сохранён, старых channel-oriented фраз в них нет. | passed |
| Поиск old/new username с ручной классификацией | `@mtproto_keys` в пользовательском runtime сохранён только в новостных приглашениях. Остальные старые вхождения — неизменённая historical migration, migration input и regression fixtures/assertions. | passed |
| Проверка migration isolation | `0012` выбирает только `sorry_server_error`, заменяет первое точное support-вхождение и сохраняет только `text`; regression test сравнивает остальные поля и весь `invite_to_channel`. | passed |
| Итоговый diff и task packet | Production/test/migration diff ограничен разрешёнными файлами `ACC-B1`; F2/F3 не затрагивают forbidden/non-goal paths. | passed |
| `git diff --check` на текущем tracked diff | Exit code 0. | passed |

Точное имя новой data migration:
`notifications.0012_update_sorry_server_error_support` — файл
`src/apps/notifications/migrations/0012_update_sorry_server_error_support.py`,
dependency `notifications.0011_seed_crypto_purchase_templates`.

## Трассировка бизнес-требований

| Требование | Реализующий код или контракт | Подтверждающий тест | Наблюдаемый результат | Статус |
|---|---|---|---|---|
| BR-001 — убрать из пользовательских сообщений контекст обхода ограничений и блокировок | `bot/src/messages.py`; `src/apps/notifications/services/broadcast_proxy_links_service.py` | `test_info_answers_callback`; `TestBroadcastProxyLinksService.test_send_links` | Текущий FAQ не содержит `обходит ограничения`/`блокировок`; broadcast не содержит `из-за блокировок`/`обойти ограничения`, сохраняя сообщение о стабильной работе и компенсации. | passed |
| BR-002 — использовать точный approved FAQ-ответ | `FAQ_TEXT` в `bot/src/messages.py` | F3 exact `test_info_answers_callback`: TDD 1 failed → 1 passed; definitive reviewer 1 passed | Пользователь видит посимвольно точный текст: `Прокси помогает Telegram работать стабильнее и уменьшает потери при плохом интернете, защищает трафик. Максимальная скорость зависит от твоего интернета.` Подходящий emoji сохранён. | passed |
| BR-003 — все обращения за помощью направить на новый username и URL | `SUPPORT_URL`; FAQ footer; bot payment fallbacks; bot/users/vds exceptions; migration `0012_update_sorry_server_error_support` | F2 bot handler suite; app-local exact exception tests; migration-test | Кнопка открывает `https://t.me/mtprotokeys_support`; support call sites и persisted `sorry_server_error` используют `@mtprotokeys_support`. F2 support wording сохранён после F3. | passed |
| BR-004 — сохранить `@mtproto_keys` только для новостных приглашений | Неизменённые `KEY_GENERATED_TEXT` и `src/apps/users/tasks.py`; migration не меняет `invite_to_channel` | `test_info_answers_callback`; migration-test | Пользовательские news invitations сохраняют `@mtproto_keys`; support-copy старого username не показывает. Historical migration source и regression fixtures не являются runtime support output. | passed |
| BR-005 — обновить существующий `sorry_server_error` новой data migration | `notifications.0012_update_sorry_server_error_support` через historical model и `RunPython` | `TestSorryServerErrorSupportMigration.test_updates_only_sorry_server_error_support_contact` | При переходе 0011→0012 первое точное support-вхождение заменяется; другие поля `sorry_server_error` и весь `invite_to_channel` остаются прежними. F3 migration не меняет. | passed |
| BR-006 — не проверять username по сети | Scope Contract и локальный diff без availability-check/settings/dependency changes | F2 bot/backend/migration suites и F3 targeted test проходят без username network check | Доступность/существование username не запрашивается и не является условием тестов или выпуска. | passed |

## Трассировка критериев приёмки

| Критерий | Реализующий код или контракт | Подтверждающий тест | Наблюдаемый результат | Статус |
|---|---|---|---|---|
| AC-001 (BR-001, BR-002) | `FAQ_TEXT`; `BroadcastProxyLinksService` user text | F3 exact `test_info_answers_callback`: 1 passed; F2 `TestBroadcastProxyLinksService.test_send_links` baseline | FAQ содержит полный approved ответ с финальной точкой и без запрещённого контекста; broadcast нейтрален и сохраняет стабильную работу, трёхдневную компенсацию и expiry. | passed |
| AC-002 (BR-003) | `SUPPORT_URL = "https://t.me/mtprotokeys_support"`; существующая кнопка использует константу | F2 `test_mtproxy_menu_links_to_site_and_support` baseline; текущий diff inspection | Кнопка «Поддержка» ведёт на точный новый URL; F3 этот код не меняет. | passed |
| AC-003 (BR-003, BR-004) | Все назначенные support call sites используют новый username; F2 исправляет channel-oriented copy в трёх exceptions; news strings неизменны | F2 bot handler suite; exact users/vds exception tests; migration-test; текущий diff inspection | Все проверенные обращения за помощью содержат новый contact; три F2 errors говорят `напишите в поддержку: @mtprotokeys_support`; news invitations продолжают содержать `@mtproto_keys`. F3 меняет только FAQ punctuation/assertion. | passed |
| AC-004 (BR-004, BR-005) | Migration `0012` выбирает только `sorry_server_error` и сохраняет только `text`; `invite_to_channel` не записывается | F2 migration regression test и isolation pair 2/2; текущий diff inspection | В `sorry_server_error` меняется только support contact; прочие поля и весь `invite_to_channel`, включая news username, сохранены. F3 migration не меняет. | passed |
| AC-005 (BR-006) | Diff не добавляет availability-check/network dependency | Финальные F3 full bot 95/95, full Django 470/470, Compose exit 0 и exact targeted test 1/1 | Все финальные проверки зелёные без username availability-check или иной новой сетевой зависимости. | passed |

## Аудит non-goals и границ task packet

- README, bot README, внутренние/исторические документы и historical migrations
  не изменены.
- Внешний Telegram-канал и его содержимое не затронуты.
- Технические DB/ORM-locking тексты не изменены.
- Тарифы, API, модели и поведение VPN/MTProxy/MTProto не изменены; изменён только
  утверждённый user-facing copy.
- Username availability-check отсутствует.
- Рефакторинга, новых abstractions, settings и dependencies нет.
- `apps/music/` не затронут.
- ACC-001/ACC-002, F2 и F3 находятся в разрешённых production/test/migration
  файлах; `scope_revision` и назначенные BR/AC совпадают с task packets.

## Отклонения и находки

- **failed BR/AC:** нет.
- **unverified BR/AC:** нет; AC-005 подтверждён свежим полным F3 root
  integration run.
- **blocking_in_scope:** нет; прежний `ACC-B1-F2` исправлен, а `ACC-B1-F3`
  восстановил точную FAQ punctuation.
- **scope_change_request:** нет.
- **Отклонения от исходной цели или out-of-scope поведение в diff:** нет.
- **follow_up:** нет; новые требования и edge cases не создавались.

## Post-acceptance release gate

Финальный root integration rerun выполнен на F3 snapshot командами:

```bash
(cd bot && uv run pytest -q)
make test
docker compose -f docker-compose.yml config --quiet
git diff --check
git status --short
```

Результаты: bot 95 passed, Django 470 tests `OK`, Compose validation и
`git diff --check` завершились с exit code 0.

## Итоговый продуктовый вердикт

**accepted** — текущий F3 результат реализует BR-001–BR-006 и AC-001–AC-005
Scope Contract revision 2. FAQ совпадает с approved текстом, включая финальную
точку; F2 support wording, news invitations и migration isolation сохранены;
сетевой проверки username и нарушений non-goals нет. Definitive batch review
tracked diff `605820832b8b…` — approved без findings. Финальный F3 root
integration rerun завершён успешно и зафиксирован выше.
