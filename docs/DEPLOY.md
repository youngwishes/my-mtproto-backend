# Релиз через Ansible

Все команды выполняются из корня репозитория.

## Однократная подготовка

```bash
cp ansible/inventory/production.ini.example ansible/inventory/production.ini
cp ansible/group_vars/mtproto_keys.yml.example ansible/group_vars/mtproto_keys.yml
```

Проверь адрес сервера и остальные значения в созданных файлах. Они содержат
production-настройки и не добавляются в Git.

Проверь доступ к серверу:

```bash
ansible -i ansible/inventory/production.ini mtproto_keys -m ansible.builtin.ping \
  --private-key ~/.ssh/id_ed25519_deploy
```

## Новый релиз

1. Убедись, что рабочее дерево содержит только изменения релиза, и запусти тесты:

   ```bash
   git status --short
   make test
   docker compose -f docker-compose.yml config --quiet
   ```

2. Убедись, что изменения прошли workflow из `docs/DEVELOPMENT_WORKFLOW.md`, Pull
   Request одобрен и merged в `main`. Прямой push релиза в `main` запрещён.
   Получи SHA merge commit через GitHub CLI и сверь его с `origin/main`:

   ```bash
   gh auth status
   PR_NUMBER=<merged-pr-number>
   test "$(gh pr view "$PR_NUMBER" --json state --jq '.state')" = MERGED
   RELEASE_SHA="$(gh pr view "$PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')"
   git fetch origin main
   test "$(git rev-parse origin/main)" = "$RELEASE_SHA"
   ```

3. Проверь playbook для опубликованного SHA:

   ```bash
   ansible-playbook -i ansible/inventory/production.ini ansible/deploy.yml \
     --syntax-check -e deploy_revision="$RELEASE_SHA" \
     --private-key ~/.ssh/id_ed25519_deploy
   ```

4. Разверни этот SHA:

   ```bash
   ansible-playbook -i ansible/inventory/production.ini ansible/deploy.yml \
     -e deploy_revision="$RELEASE_SHA" \
     --private-key ~/.ssh/id_ed25519_deploy
   ```

5. Успешный запуск должен завершиться с `failed=0`. Дополнительно проверь сайт и
   запущенный SHA через хост из Ansible inventory:

   ```bash
   curl --fail --silent --show-error https://beatvault.ru/ >/dev/null
   ansible -i ansible/inventory/production.ini mtproto_keys \
     --private-key ~/.ssh/id_ed25519_deploy \
     -m ansible.builtin.shell \
     -a 'git -C /root/my-mtproto-backend rev-parse HEAD && cd /root/my-mtproto-backend && docker compose ps'
   ```

Playbook сам запускает миграции через entrypoint Django, проверяет HTTP-ответ и
состояние всех Compose-сервисов. При ошибке он возвращает предыдущий код и
контейнеры. Уже применённые миграции БД автоматически не откатываются; перед
ручным откатом проверь их совместимость и состояние backup в Litestream.

Перед общим `docker compose up` playbook отдельно останавливает старый
`vpn-payment-worker`, затем запускает единственный новый worker очереди
`vpn_payment_fulfillment`. Он монтирует тот же `./data`, что и Django/SQLite, и
до старта Celery получает lifetime lock
`/app/data/vpn-payment-worker.owner.lock`. Дублирующий процесс завершается, не
начав слушать очередь. Отдельный transaction lock
`/app/data/vpn-payment-writer.lock` удерживается только при применении receipt;
healthcheck его не трогает, а проверяет owner PID, command identity и занятость
lifetime lock. Поэтому корректный worker остаётся healthy во время транзакции.
Playbook требует `vpn-payment-worker` в live ignored group vars и ждёт Docker
`healthy`; при rollback failed singleton останавливается до восстановления
предыдущего Compose stack. Не запускай второй singleton вручную.

Retry receipt настраивается `VPN_PAYMENT_RETRY_BASE_SECONDS`,
`VPN_PAYMENT_RETRY_MAX_SECONDS` и `VPN_PAYMENT_RETRY_JITTER_SECONDS` из
`.env.example`. Delay экспоненциально растёт по сохранённому `attempt_count` и
ограничивается max. Startup/task composition fail-fast требует целый base > 0,
base <= max <= 86 400 и конечный jitter в диапазоне 0..300 секунд; значения не
нормализуются автоматически. После ошибки проверяй, что receipt
перешёл из `PROCESSING` в `RETRY`, `next_attempt_at` наступает в будущем, а
`last_error_code` содержит только стабильный код без текста исключения.

Для public VPN subscription задай `VPN_SUBSCRIPTION_REDIS_URL`, rate limit и
window из `.env.example`. В `VPN_SUBSCRIPTION_TRUSTED_PROXY_NETWORKS` перечисляй
только фактические IPv4/IPv6 CIDR reverse proxy: иначе `X-Forwarded-For`
игнорируется. Edge Nginx перезаписывает XFF через `$remote_addr`.
Subscription access log содержит только статический route label, status и
latency; `$request_uri`, `$uri` и `$args` добавлять нельзя, потому что token —
bearer credential.

Safe subscription location присутствует в HTTP и HTTPS server block:
оба перезаписывают входной XFF значением `$remote_addr` и пишут telemetry только
в `/dev/stdout`, чтобы контейнер не требовал writable log-файл. HTTP location
только возвращает `308` на тот же path/query по HTTPS и никогда не proxy-ирует
bearer token в Django по plaintext; subscription отдаёт только HTTPS location.

## VPN observability runbook

Flower хранит ограниченную историю до 10 000 задач в
`/app/data/flower.db`; UI остаётся за Basic Auth и доступен только через Nginx.
Проверяй ежеминутную `apps.vpn.collect_observability`, reconcile/health и
notification tasks. Logs содержат `vpn_metric`/`vpn_alert` events без resource
identifier и секретов. Redis используется только для alert dedupe; его сбой не
должен останавливать payment/reconcile/notification business paths.
В dashboard суммируй только `_total` events; `_current` отображай как gauges.
Проверь reconcile delivery и notification success/failure totals, lease recovery
total и отсутствие labels/IDs. Receipt collector выполняет одну SQL aggregation
и выбирает максимум 100 stale candidates за tick.

| Alert code | Проверка и действие оператора |
|---|---|
| `stale_receipt` | Проверить singleton worker/Beat/Redis, затем RECEIVED/RETRY/PROCESSING age; receipt вручную не удалять. |
| `no_ready_node` | Не включать продажи; проверить health, exact revision/hash и data plane хотя бы двух нод. |
| `incompatible_contract` | Сверить backend/agent SHA и compatibility matrix; mutation не повторять до совместимого agent. |
| `snapshot_too_large` | Оставить ноду вне выдачи, проверить entry/byte capacity и добавить capacity до включения продаж. |
| `revision_drift` | Сверить desired/applied revision/hash и full reconcile; partial/manual snapshot запрещён. |
| `agent_unauthorized` | Проверить lookup key/secret и management allowlist без вывода Authorization. |
| `agent_tls_failure` | Проверить DNS, certificate chain/SAN/expiry и системное время; TLS verification не отключать. |
| `notification_failure` | Проверить Telegram/broker; marker не продвигать вручную, Beat обеспечит at-least-once retry. |

Пороги задаются четырьмя `VPN_OBSERVABILITY_*` переменными из `.env.example`.
Изменение порога должно сохранять bounded cardinality и не добавлять URI,
UUID/token, provider payload, Authorization или snapshot body в logs/alerts.
Drift/auth/TLS thresholds считаются от persisted onset fields, не от
`last_health_at`. После expand migrations legacy timestamps backfilled из
`updated_at` как conservative approximation; проверь их до включения alerts.
Пока старый backend может писать после expand, NULL `applied_at`/receipt
`ready_at` не теряется: collector использует bounded per-row fallback к
`updated_at` только
для APPLIED/READY. Это приблизительное время old-writer; новые writers пишут
exact transition timestamp. Отдельного repair scan в rollout нет.
