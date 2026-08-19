# VPN

## Зона ответственности

Отдельный VPN-продукт: подписка пользователя, subscription URL, профили HAPP и
доставка credentials на VPN-ноды. Пользовательские правила находятся в
[BUSINESS.md](../BUSINESS.md), API — в [CONTRACTS.md](../CONTRACTS.md), модели —
в [MODELS.md](../MODELS.md).

## Карта компонентов

- VPNSubscription, VPNInstance — подписка и ноды.
- purchase/menu/reissue services — lifecycle пользовательской подписки.
- subscription builder — выдача профилей по публичному token.
- profile scheduling/infra services — асинхронная доставка на ноды.
- tasks.py — delivery, retry, health и reconcile.

## Зависимости

Использует users, payments product/payment boundaries и core transport. Бот
потребляет VPN API, не обращаясь к нодам напрямую.

## Границы

VPN не переиспользует MTProxy-модели. Node readiness не входит в синхронный
purchase response; недоступность ноды не откатывает подтверждённый платёж.
