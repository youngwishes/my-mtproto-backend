# Главное меню продуктов — приёмка

- **Статус:** accepted
- **Scope revision:** 2
- **Проверенный base:** `c0c84a8f2bee26efeba6d3a5f18274b49c94b665`
- **Проверенный implementation head:** `1bda808730d74c22f2cea511250529231e140017`

## Результат

Корневой экран Telegram-бота показывает нейтральный выбор между MTProxy и VPN.
MTProxy открывает существующий дружелюбный текст и утверждённое меню действий.
VPN открывает отдельный дружелюбный экран с зелёной кнопкой «Купить VPN»,
кнопками «Моя подписка» и «Назад».

Покупка VPN предлагает только оплату картой и Telegram Stars, не запрашивая
статус подписки. Экран «Моя подписка» отдельно показывает активный или истёкший
статус, дату окончания и сохранённую subscription-ссылку. Если подписки нет,
бот сохраняет меню VPN и отправляет отдельное сообщение с каналом связи
`@mtproto_keys`. Успешная оплата и инструкция подключения через HAPP не
изменены.

## Покрытие требований

| Требования | Доказательство | Результат |
|---|---|---|
| BR-001–BR-005; AC-001–AC-004 | Тесты `/start`, consent completion, root callback, repeated MTProxy entry, точного порядка строк и всех MTProxy Back-кнопок | passed |
| BR-006; AC-005–AC-006 | Точный дружелюбный текст VPN, три строки кнопок, `success`-стиль покупки и контекстные возвраты | passed |
| BR-007; AC-010 | Buy callback создаёт card и Stars invoices, не читает VPN status; callback уведомления о продлении сохранён | passed |
| BR-008, BR-011–BR-012; AC-011–AC-012 | Subscription callback читает status без invoices; active/expired показывают дату, URL и ровно одну Back-кнопку | passed |
| BR-013–BR-014; AC-013 | При отсутствии подписки нет invoices/edit; отдельное точное service-error сообщение содержит `@mtproto_keys` | passed |
| BR-009–BR-010, BR-015; AC-007–AC-009 | Юридические, referral, MTProxy и VPN payment-success/HAPP сценарии сохранены; полные regression suites зелёные | passed |

## TDD и batch review

- PMM-B1: RED на отсутствующих root/MTProxy interfaces и неверных MTProxy Back
  callbacks; GREEN — целевые `12 passed` и `3 passed`; batch commit `a134ce7`;
  независимый `code-reviewer`: `VERDICT: approved`, findings отсутствуют.
- PMM-B2: RED на отсутствующем `process_vpn_menu`; GREEN — VPN `10 passed` и
  полный `test_handlers.py` `45 passed`; batch commit `1aed943`;
  независимый `code-reviewer`: `VERDICT: approved`, findings отсутствуют.
- PMM-B3: RED на прежнем VPN menu/status flow и отсутствующем subscription
  handler; GREEN — целевые `5 passed`, полный `test_handlers.py` `43 passed`;
  batch commit `1bda808`; независимый `code-reviewer` проверил exact SHA и
  завершил с `VERDICT: approved`, findings отсутствуют.

## Интеграционные проверки

Выполнены на `1bda808730d74c22f2cea511250529231e140017`:

```text
cd bot && uv run pytest -q
88 passed

make test
367 passed; System check identified no issues

docker compose -f docker-compose.yml config --quiet
exit 0

git diff --check
exit 0, output empty
```

## Product review

Независимый `product-reviewer` сопоставил интегрированный diff с
BR-001–BR-015 и AC-001–AC-013 на exact SHA
`1bda808730d74c22f2cea511250529231e140017`:

- `blocking_in_scope`: нет;
- `scope_change_request`: нет;
- `follow_up`: нет;
- итог: `VERDICT: accepted`.

Backend API, модели, миграции, цены, payment handlers, глобальные архитектурные
контракты и `apps/music/` не изменялись. Пользовательские изменения заголовка
`VPNSubscriptionView` не входят в feature diff. Отдельный архитектурный документ
не требовался согласно утверждённому Scope Contract.
