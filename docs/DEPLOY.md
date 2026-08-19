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

1. Выполни repository checks:

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

4. Остановись и запроси новое явное разрешение пользователя непосредственно
   перед deploy. Назови `RELEASE_SHA`, результаты тестов и существенные риски.
   Разрешение на merge или предыдущий deploy не считается разрешением на этот
   запуск playbook.

5. Только после такого разрешения разверни этот SHA:

   ```bash
   ansible-playbook -i ansible/inventory/production.ini ansible/deploy.yml \
     -e deploy_revision="$RELEASE_SHA" \
     --private-key ~/.ssh/id_ed25519_deploy
   ```

6. Успешный запуск должен завершиться с `failed=0`. Проверь `nginx -t`, SHA и
   все Compose-сервисы через хост из Ansible inventory, затем внешние HTTPS и
   HTTP-to-HTTPS redirect для `dash.mtprotokeys.com` и `beatvault.ru`:

   ```bash
   curl --fail --silent --show-error https://dash.mtprotokeys.com/ >/dev/null
   curl --fail --silent --show-error https://beatvault.ru/ >/dev/null
   ansible -i ansible/inventory/production.ini mtproto_keys \
     --private-key ~/.ssh/id_ed25519_deploy \
     -m ansible.builtin.shell \
     -a 'git -C /root/my-mtproto-backend rev-parse HEAD && cd /root/my-mtproto-backend && docker compose ps && docker exec nginx nginx -t'
   ```

Проверь, что HTTP каждого Django-host перенаправляется на свой HTTPS-host, а
`flower.mtprotokeys.com` по HTTPS без credentials отвечает `401` и с credentials
из защищённого окружения отвечает успешно. Playbook сам запускает миграции через
entrypoint Django, проверяет HTTP-ответ и состояние всех Compose-сервисов. При
ошибке он автоматически возвращает предыдущий SHA/Compose stack. Уже
применённые миграции БД автоматически не откатываются; перед ручным откатом
проверь их совместимость и состояние backup в Litestream.

## Crypto Pay: production-конфигурация и rollback

Crypto Pay использует только backend `.env`: `CRYPTOPAY_API_TOKEN`,
`CRYPTOPAY_WEBHOOK_SECRET`, опциональный `CRYPTOPAY_BASE_URL` и стандартный
`CRYPTOPAY_REQUEST_TIMEOUT=5`. Bot `.env` этих значений не содержит. Секреты и
секретная часть webhook URL не попадают в Git, логи или командную историю.
Обычный релиз не требует повторной проверки этой конфигурации или provider
callback.

При rollback развернуть предыдущий совместимый SHA тем же Ansible playbook как
один whole-stack release: прежний bot скроет Crypto Pay-кнопки, а backend
вернётся вместе с ним. Additive migration, backend env и provider webhook
оставить: без Crypto Pay-кнопок они безвредны и не требуют ручного Compose или
component-level rollback. Не удалять и не откатывать реальные `Payment` или
`CryptoPaymentIntent` строки и не менять продукты. Merge и production deploy
требуют отдельных явных разрешений.

## Platega SBP: production-конфигурация и rollback

Platega использует только Django/Celery backend `.env`:
`PLATEGA_MERCHANT_ID`, `PLATEGA_SECRET`, HTTPS `PLATEGA_BASE_URL` и положительный
`PLATEGA_REQUEST_TIMEOUT`. Bot `.env` этих значений не содержит.
`PLATEGA_CALLBACK_DEBUG_LOGGING` по умолчанию остаётся `false`. Production
credentials, значения security headers, Telegram metadata и payment URL нельзя
помещать в Git, логи или командную историю.

Для контролируемой диагностики фактического provider payload допускается
временно установить `PLATEGA_CALLBACK_DEBUG_LOGGING=true`. После одного
тестового callback забрать событие `platega_callback_request`, считать его body
чувствительным диагностическим материалом и немедленно вернуть флаг в `false`.
Событие создаётся только после успешной проверки Platega credentials и не
содержит значения `X-MerchantId`, `X-Secret`, Authorization или Cookie.

Production callback Platega направлен на
`https://dash.mtprotokeys.com/api/v1/payments/platega/callback/` с теми же
`X-MerchantId`/`X-Secret`. Endpoint аутентифицирует оба raw header до body
parsing; redirects успеха и ошибки ведут в `BOT_LINK`, но не являются
доказательством платежа. Для SBP нет status GET, polling schedule или ручной
проверки.

Additive commission migration задаёт существующей строке `8.00%`, но никогда не
меняет её сохранённый `is_active`; отсутствующая строка создаётся выключенной, а
Stars/Crypto Pay сохраняют свои переключатели и получают `0.00%`.
Обычный релиз сохраняет текущие переключатели способов оплаты и не требует
выключать `platega_sbp` или повторно проверять callback.

Для штатного rollback сначала выключить toggle, подтвердить, что он остаётся
выключенным, и проверить отсутствие intent в
`creating`, `active`, `processing` и `retryable`. Пока хотя бы один такой intent
есть, откат прежнего SHA заблокирован: не заменять callback ручной выдачей и не
терять данные. После прохождения gate отключить provider callback и только
затем, по отдельному разрешению deploy, развернуть совместимый предыдущий
whole-stack SHA. Additive migration, intent/Payment rows и backend environment
остаются; реальные платежи не удаляются, migration автоматически не
откатывается. `CHARGEBACKED` не имеет rollout/recovery процедуры в этой фиче и
остаётся только unsupported safe acknowledgement.

## VPN: production-конфигурация

VPN использует `VPN_SUBSCRIPTION_BASE_URL=https://dash.mtprotokeys.com` и
защищённый `VPN_AGENT_TOKEN` вне Git. Обычный релиз не повторяет первоначальный
rollout node-agent, transport, `VPNInstance` и товара `vpn_30d`.

В текущем MVP `VPNInstance.management_url` указывает на публичный plaintext HTTP
management proxy ноды. Host firewall отсутствует; bearer token и route allowlist
остаются. Риск перехвата token/profile payload принят пользователем.
