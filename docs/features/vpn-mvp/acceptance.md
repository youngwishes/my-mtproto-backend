# VPN MVP — acceptance

## Статус

- Scope Contract: `scope_revision: 1`.
- Product review: `accepted`.
- Дата автоматизированной приёмки: 31 июля 2026 года.
- Проверенные implementation heads:
  - backend и bot: `18813d2debcff168dc66f2b118344bed46331e24`;
  - node-agent: `6799b27f21689ff57b11ca69f0148337b45f51ae`.
- Production deploy и ручные release-проверки не выполнялись.

## Автоматизированная приёмка

| Область | Результат |
|---|---|
| Django backend | `make test` — 365 tests, OK |
| Telegram bot | `uv run pytest` — 90 passed |
| Node-agent и deploy contracts | `uv run pytest` — 45 passed |
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
- exact-revision deploy, private management bind и allow-list backend source;
- отсутствие WebSocket и сохранность существующих MTProto-сценариев.

Независимый product review не выявил `blocking_in_scope`,
`scope_change_request` или `follow_up` findings. Все BR-001…BR-019 и
AC-001…AC-011 приняты на уровне кода и автоматизированных контрактов.

## Ручные release-gates

После отдельного разрешения на merge и нового отдельного разрешения на deploy
нужно выполнить на первой ноде и записать результат:

1. развернуть exact release SHA и проверить bootstrap, private management route
   и firewall allow-list;
2. создать неактивную `VPNInstance`, выполнить повторяемый backfill и проверить
   PUT профиля;
3. импортировать одну subscription URL в HAPP и подтвердить `2 × N` профилей;
4. проверить TCP/443 VLESS+REALITY и UDP/443 Hysteria 2;
5. выполнить реальные оплаты ЮKassa и Stars, подтвердив немедленную выдачу URL;
6. проверить продление, административную деактивацию и expiry DELETE;
7. активировать ноду и продажи только после успешного smoke.

Ни один из этих пунктов не отмечен выполненным в pre-PR приёмке. Первый сервер
не изменялся и production deploy не запускался.

## Отложено за рамки MVP

Reconcile/recovery workers, persistent DB агента, device/traffic limits,
несколько тарифов, trial, reissue, server selection, metrics/self-healing,
автоматические refunds/rollback и WebSocket остаются явными non-goals.
