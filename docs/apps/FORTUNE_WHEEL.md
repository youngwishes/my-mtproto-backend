# Fortune wheel

## Зона ответственности

Telegram Mini App колеса фортуны: проверка подписанных Telegram init data,
240-часовое ограничение, выбор и атомарное начисление apple-приза, журнал
успешных вращений и пользовательский экран. Правила находятся в
[BUSINESS.md](../BUSINESS.md#колесо-фортуны), wire-контракты — в
[CONTRACTS.md](../CONTRACTS.md#fortune-wheel-mini-app), модель — в
[MODELS.md](../MODELS.md#fortunespin-appsfortunewheel).

## Карта компонентов

- `FortuneSpin` — журнал успешных результатов.
- `SpinFortuneWheelService` — cooldown, случайный выбор, транзакция начисления.
- `GetFortuneWheelStatusService` — последний приз и следующая доступность.
- `TelegramMiniAppAuthentication` — HMAC и freshness boundary для `initData`.
- API views — status/spin transport mapping.
- Template и static assets — 3D-колесо, анимация, countdown и haptic feedback.
- `FortuneSpinAdmin` — диагностика и ручная корректировка существующей истории;
  добавление и удаление строк запрещены.

## Зависимости

- `users.SystemUser` — юридическое согласие и mutable `apple_balance`.
- `core.BaseDjangoModel`, DTO и базовые исключения.
- Django REST Framework и серверный `BOT_TOKEN`.
- Telegram Mini Apps JavaScript bridge в браузере пользователя.

## Границы

Frontend не выбирает приз, не передаёт Telegram ID и не меняет доступность.
Bot не начисляет яблоки и не получает результат отдельным сообщением.
Приложение не владеет оплатой, обменом яблок на дни или MTProxy lifecycle.
