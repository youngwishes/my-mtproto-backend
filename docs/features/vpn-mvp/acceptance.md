# VPN MVP — acceptance

## Статус

- Scope Contract: `scope_revision: 2`.
- Product review: `accepted`.
- Дата автоматизированной приёмки: 1 августа 2026 года.
- Production releases:
  - backend и bot: `5f53902d5bef27d7fa128b1980361bd10a7bbb58`;
  - node-agent: `a877e985c7d1611c7dc4d78ce85044ab62a738ae`.
- Production deploy и control-plane smoke выполнены 1 августа 2026 года.

## Автоматизированная приёмка

| Область | Результат |
|---|---|
| Django backend | `make test` — 367 tests, OK |
| Telegram bot | `uv run pytest` — 90 passed |
| Node-agent и deploy contracts | `uv run pytest` — 62 passed |
| Backend Compose | production config valid |
| Node-agent Compose | production и local configs valid |
| Node-agent deploy | Ansible syntax-check valid |
| Xray runtime | pinned 26.7.11; rendered config — `Configuration OK` |
| Рабочие деревья | `git diff --check` clean в обоих репозиториях |

Автоматизированные проверки подтверждают:

- отдельный VPN-раздел и актуальные администраторские цены ЮKassa/Stars;
- 30-дневную идемпотентную покупку и продление без смены subscription URL и
  credentials;
- немедленную выдачу URL и краткой инструкции HAPP после фиксации платежа;
- детерминированные `2 × N` профилей VLESS+REALITY и Hysteria 2;
- асинхронные PUT/DELETE с retry и terminal alert администратору;
- пустую subscription после истечения или деактивации;
- три VPN-уведомления, единственное admin-действие деактивации и повторяемый
  backfill неактивной ноды;
- stateless agent, bounded startup bootstrap, Xray runtime API и локальную
  Hysteria HTTP auth;
- exact-revision deploy, публичный path-filtered management proxy с bearer
  auth и недоступность Hysteria `/auth` через management ingress;
- отсутствие WebSocket и сохранность существующих MTProto-сценариев.

Независимый product review не выявил `blocking_in_scope`,
`scope_change_request` или `follow_up` findings. Все BR-001…BR-019 и
AC-001…AC-011 приняты на уровне кода и автоматизированных контрактов.

## Production release

Выполнено после отдельных разрешений на merge и deploy:

1. На первой ноде развёрнут exact node-agent release. Публичный management
   ingress отвечает на TCP/8443; plaintext HTTP и отсутствие host firewall
   приняты как риск MVP. Bearer auth возвращает `401` без токена, а `/auth`
   недоступен через management proxy (`404`).
2. Создана неактивная `VPNInstance` `VPN-1`, выполнен backfill. Активных
   подписок на момент backfill не было.
3. Сквозной временный профиль успешно прошёл PUT (`200`), появился в Xray и
   прошёл Hysteria auth. DELETE вернул `204`, после чего профиль исчез из Xray
   и перестал проходить Hysteria auth.
4. Подтверждены listeners TCP/443 для VLESS+REALITY, UDP/443 для Hysteria 2 и
   TCP/8443 для management proxy; Xray healthcheck зелёный.
5. После успешного control-plane smoke активированы `VPN-1` и товар `vpn_30d`
   с утверждёнными ценами 149 рублей и 149 Stars. Продажи разрешены в рамках
   принятого MVP-решения.
6. Backend release и все центральные Compose-сервисы запущены; production
   backend успешно обращается к публичному health endpoint VPN-ноды.

Не выполнялись и остаются ручными post-release проверками:

- импорт реальной subscription URL в HAPP и data-plane трафик через оба
  транспорта;
- реальные оплаты ЮKassa и Stars;
- продление, административная деактивация и expiry на реальной подписке.

## Отложено за рамки MVP

Reconcile/recovery workers, persistent DB агента, device/traffic limits,
несколько тарифов, trial, reissue, server selection, metrics/self-healing,
автоматические refunds/rollback и WebSocket остаются явными non-goals.
