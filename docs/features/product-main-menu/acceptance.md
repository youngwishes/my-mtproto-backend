# Главное меню продуктов — приёмка

- **Статус:** accepted
- **Scope revision:** 1
- **Проверенный base:** `c0c84a8f2bee26efeba6d3a5f18274b49c94b665`
- **Проверенный feature head:** `1aed9437ae5559ed741a8b548f5a9a8b054c4082`

## Результат

Корневой экран Telegram-бота показывает нейтральный выбор между MTProxy и VPN.
MTProxy открывает существующий текст и утверждённое меню действий, VPN — меню с
кнопкой «Купить ВПН». Все внутренние кнопки возврата сохраняют контекст
выбранного продукта. Существующие юридический, реферальный, платёжный и
продуктовые сценарии не изменены за пределами утверждённой навигации.

## Покрытие требований

| Требования | Доказательство | Результат |
|---|---|---|
| BR-001–BR-004; AC-001–AC-003 | Тесты `/start`, consent completion, root callback, repeated MTProxy entry и точного порядка строк | passed |
| BR-005; AC-004 | Контракт всех шести существующих MTProxy Back-кнопок, root Back и сохранённый reissue cancel | passed |
| BR-006–BR-008; AC-005–AC-006 | Точный состав VPN product menu, прежний VPN status/payment screen и оба контекстных возврата | passed |
| BR-009; AC-007 | Тесты referrer callback, consent acceptance, self-referral и backend error | passed |
| BR-010; AC-008 | Регрессионные тесты серверов, reissue, free claim, gift, referral, invoice payloads и payment routing | passed |
| AC-009 | Полные bot и Django suites, Compose validation и diff check | passed |

## TDD и batch review

- PMM-B1: RED на отсутствующих root/MTProxy interfaces и неверных MTProxy Back
  callbacks; GREEN — целевые `12 passed` и `3 passed`; batch commit `a134ce7`;
  независимый `code-reviewer`: `VERDICT: approved`, findings отсутствуют.
- PMM-B2: RED на отсутствующем `process_vpn_menu`; GREEN — VPN `10 passed` и
  полный `test_handlers.py` `45 passed`; batch commit `1aed943`;
  независимый `code-reviewer`: `VERDICT: approved`, findings отсутствуют.

## Интеграционные проверки

Выполнены на `1aed9437ae5559ed741a8b548f5a9a8b054c4082`:

```text
cd bot && uv run pytest
90 passed

make test
367 passed; System check identified no issues

docker compose -f docker-compose.yml config --quiet
exit 0

git diff --check
exit 0, output empty
```

## Product review

Независимый `product-reviewer` сопоставил интегрированный diff с
BR-001–BR-010 и AC-001–AC-009:

- `blocking_in_scope`: нет;
- `scope_change_request`: нет;
- `follow_up`: нет;
- итог: `VERDICT: accepted`.

Backend API, модели, миграции, цены, payment handlers, глобальные архитектурные
контракты и `apps/music/` не изменялись. Отдельный архитектурный документ не
требовался согласно утверждённому Scope Contract.
