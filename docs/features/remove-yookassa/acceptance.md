# Product Acceptance — Telegram Stars-only Payments

- **Verdict:** accepted
- **Scope revision:** 2 (immutable)
- **Reviewed plan items / task packet:** `RYK-001`, `RYK-002` / `RYK-B1`
- **Reviewed implementation base:** `8795d29`
- **Architecture artifact:** not required by the approved plan; models, backend
  API and component interactions remain outside the change.

## Product outcome

Новые экраны покупки MTProxy, подарочного сертификата и VPN предлагают только
Telegram Stars и создают только XTR invoices. Три callback ЮKassa из ранее
отправленных сообщений остаются зарегистрированы, но только завершают callback
без invoice, backend-вызова, нового сообщения или изменения текущего.

Обработка ранее завершённых non-XTR successful payments сохранена для всех
трёх продуктов: бот использует `provider_payment_charge_id`, передаёт provider
`yukassa` в существующий fulfilment и выдаёт соответствующую услугу.

## Requirement traceability

| ID | Утверждённое требование | Реализующий код или контракт | Подтверждающий тест | Наблюдаемый результат | Статус |
| --- | --- | --- | --- | --- | --- |
| BR-001 | Новые экраны MTProxy, gift и VPN показывают только Telegram Stars. | `payment_methods()`, `gift_certificate_payment_methods()` и `vpn_payment_methods()` в `bot/src/keyboards.py`; `process_boost_paid`, `process_gift_certificate` и `process_vpn` используют эти клавиатуры; Stars handlers в `bot/src/handlers/payments.py` и `bot/src/handlers/vpn.py` создают XTR invoice. | `test_payment_screen_includes_legal_links`, `test_gift_certificate_screen_shows_payment_options`, `test_vpn_purchase_fetches_stars_invoice_and_shows_stars_only_screen`; `test_pay_stars_sends_xtr_invoice`, `test_gift_stars_invoice_uses_gift_payload`, `test_vpn_stars_invoice_uses_distinct_payload_and_vpn_product`. | Во всех трёх новых экранах единственная платёжная кнопка имеет Stars callback; отправленные invoices имеют валюту `XTR` и сохраняют product-specific payload. | passed |
| BR-002 | `pay_yukassa`, `gift_yukassa` и `vpn_pay_yukassa` являются безопасными no-op. | Три router handler в `bot/src/handlers/payments.py` и `bot/src/handlers/vpn.py` принимают только `callback` и выполняют только `await callback.answer()`. | Параметризованный `test_legacy_yukassa_callbacks_are_safe_noops` покрывает все три callback и проверяет сигнатуру, один answer, отсутствие invoice, message answer/edit и dependency parameter. | Каждый старый callback завершается без создания оплаты, backend-вызова или изменения пользовательского сообщения. | passed |
| BR-003 | Fulfilment ранее завершённых non-XTR payments и выдача услуги сохраняются. | Существующий `process_successful_payment` в `bot/src/handlers/payments.py` для non-XTR выбирает `provider_payment_charge_id` и provider `yukassa`, затем маршрутизирует обычную покупку, gift и оба VPN payload в прежние confirmation contracts. | `test_successful_payment_preserves_provider_and_charge_id`, `test_successful_gift_payment_returns_code_to_forward`, non-XTR case в `test_successful_vpn_payment_routes_only_to_vpn_buy_and_shows_happ_import`. | MTProxy подтверждается с card charge ID; gift возвращает код; VPN возвращает срок и subscription URL; во всех non-XTR cases provider равен `yukassa`. | passed |
| AC-001 | Ни один новый экран не содержит callback ЮKassa; доступна только Stars-кнопка. | Точные клавиатуры трёх продуктов в `bot/src/keyboards.py`; VPN screen получает только Stars invoice в `process_vpn`. | Три exact-keyboard tests для MTProxy, gift и VPN. | Наблюдаемые callback-наборы: `pay_stars`, `gift_stars`, `vpn_pay_stars` плюс соответствующая Back-кнопка; callback ЮKassa отсутствует. | passed |
| AC-002 | Каждый legacy callback вызывает `callback.answer()` без invoice, backend call, send или edit. | Три однопараметрических no-op handler, зарегистрированных на исходных callback strings. | Три case в `test_legacy_yukassa_callbacks_are_safe_noops`; тест вызывает handler без `Dependencies` и проверяет все запрещённые эффекты. | Для каждого case зафиксирован ровно один callback answer и пустые collections сообщений, edits и invoices. | passed |
| AC-003 | Автотесты подтверждают Stars-сценарии всех продуктов и legacy non-XTR fulfilment. | Stars invoice mapping в `PaymentsClient`; product handlers сохраняют Stars payloads; `process_successful_payment` сохраняет non-XTR routing для MTProxy, gift и VPN. | Targeted suite: 55 passed; полный bot suite: 86 passed. В них присутствуют Stars invoice tests всех трёх продуктов и non-XTR tests всех трёх fulfilment routes. Полный Django suite: 367 passed. | Все утверждённые Stars и compatibility scenarios выполняются, смежный backend suite не выявил регрессий. | passed |

## Scope, non-goals, and deviations

Проверен актуальный `scope_revision: 2`; task packet `RYK-B1` назначает все
BR-001–BR-003 и AC-001–AC-003 двум последовательным пунктам плана. Implementation
diff относительно `8795d29` содержит ровно 18 разрешённых существующих файлов:
bot presentation/handlers/payment client/wiring, назначенные тесты и продуктовую
документацию.

Diff отсутствует в backend production/tests, моделях, enum, миграциях, API и
контрактах, `integration_tests/`, `docs/ARCHITECTURE.md`, `docs/CONTRACTS.md`,
`docs/MODELS.md`, `apps/music/` и отдельном revert-test. Исторические платёжные
данные, backend contracts, Stars payloads, цены и правила выдачи услуг не
изменены. Старые invoices не отменяются; legacy callback не показывает новый
текст, что соответствует non-goals.

Failed или unverified утверждённых пунктов нет. Нарушений non-goals,
out-of-scope поведения в implementation diff и отклонений от исходной
продуктовой цели не обнаружено.

## Evidence

- Implementer зафиксировал ожидаемый TDD RED: 3 failures для Stars-only экранов
  и отдельные 3 failures из-за отсутствующих legacy handlers; затем targeted
  GREEN — 55 passed.
- Независимый batch `code-reviewer` проверил exact 18-file diff, targeted suite
  (55 passed), полный bot suite (86 passed), Compose config и diff boundaries;
  итог — approved, `blocking_in_scope` отсутствуют.
- Свежая product-review verification: targeted suite — 55 passed; полный bot
  suite — 86 passed; `make test` — 367 passed, Django system check без ошибок;
  `docker compose -f docker-compose.yml config --quiet` — exit 0;
  `git diff --check 8795d29` — clean; forbidden-path diff — пустой.

## Risks and follow-up

Batch reviewer отметил `scope_change_request`: существующий
`integration_tests` harness всё ещё ссылается на удалённый card API бота.
`integration_tests/` прямо запрещён task packet и не входит ни в один
утверждённый BR/AC; оркестратор отклонил расширение текущего scope. Поэтому это
не является основанием для rejection. При необходимости синхронизация harness
может быть выполнена как необязательный `follow_up` в отдельной задаче с новым
Scope Contract.
