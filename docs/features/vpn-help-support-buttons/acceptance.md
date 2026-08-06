# Ссылки на настройку и поддержку в VPN-меню — приёмка

- **Статус:** accepted
- **Scope revision:** 1
- **Проверенная база:** `9d96fc31aceafa62cc91b8e63f3cff34b84afac9`

## Результат

VPN-меню сохраняет существующие действия покупки и просмотра подписки, затем
показывает отдельные URL-кнопки «📖 Как настроить» и «💬 Поддержка», после
которых последней строкой остаётся «🔙 Назад». Новые кнопки не создают callbacks
и ведут на утверждённые URL.

## Покрытие требований

| Требования | Доказательство | Результат |
|---|---|---|
| BR-001; AC-001–AC-002 | Строка «📖 Как настроить» ведёт на `https://mtprotokeys.ru/vpn/`, не имеет callback/style и занимает отдельную строку | passed |
| BR-002; AC-001–AC-002 | Строка «💬 Поддержка» ведёт на `https://t.me/mtprotokeys_support`, не имеет callback/style и занимает отдельную строку | passed |
| BR-003; AC-001 | Exact-contract test проверяет пять однокнопочных строк и все поля `text`, `callback_data`, `url`, `style` в утверждённом порядке | passed |

## TDD и batch review

- RED: targeted test завершился `1 failed`, потому что фактическое меню ещё
  содержало три строки и не имело двух новых URL-кнопок.
- GREEN: та же targeted-команда завершилась `1 passed` после минимального
  production-изменения.
- Независимый `code-reviewer`: `blocking_in_scope`, `scope_change_request` и
  `follow_up` отсутствуют; `VERDICT: approved`.
- Рабочее дерево и hash implementation diff до и после batch review совпали.

## Интеграционные проверки

Выполнены на feature-ветке `codex/vpn-help-support-buttons`:

```text
cd bot && uv run pytest tests/test_handlers.py::test_vpn_product_menu_uses_approved_copy_and_actions -q
1 passed

cd bot && uv run pytest -q
95 passed

make test
470 tests passed; System check identified no issues

docker compose -f docker-compose.yml config --quiet
exit 0

git diff --check
exit 0
```

## Scope check

Implementation diff ограничен `bot/src/messages.py`, `bot/src/keyboards.py` и
`bot/tests/test_handlers.py`. Feature docs находятся только в
`docs/features/vpn-help-support-buttons/`. Handlers, callbacks, backend, модели,
миграции, платежи, другие меню, VPN copy, environment/config, архитектура и
`apps/music/` не изменялись. Merge и deploy не выполнялись.

## Product review

Независимый `product-reviewer` сопоставил реализацию и exact-contract test со
всеми BR-001–BR-003 и AC-001–AC-002: каждый пункт получил `passed`, non-goals
соблюдены, находки отсутствуют. Итог: `VERDICT: accepted`.
