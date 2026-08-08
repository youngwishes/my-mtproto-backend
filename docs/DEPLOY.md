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

6. Успешный запуск должен завершиться с `failed=0`. Дополнительно проверь сайт и
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

## Crypto Pay rollout и rollback

До release задать только в backend `.env` значения `CRYPTOPAY_API_TOKEN`,
`CRYPTOPAY_WEBHOOK_SECRET` и при необходимости `CRYPTOPAY_BASE_URL`; bot `.env`
не получает эти переменные. Оставить `CRYPTOPAY_REQUEST_TIMEOUT=5`, если иной
операционный таймаут не согласован. Не добавлять значения в Git, логи или
командную историю.

В рамках обычного подготовленного релиза до запуска существующего Ansible
playbook заполнить backend `.env` и настроить в кабинете Crypto Pay HTTPS webhook
на `https://<public-host>/api/v1/payments/crypto/webhooks/<webhook-secret>/`.
Секрет URL хранится только вне Git; новый endpoint дополнительно проверяет HMAC.
До выпуска прежний bot не показывает Crypto Pay-кнопок, поэтому счета ещё не
создаются.

Затем один раз развернуть проверенный `RELEASE_SHA` существующим Ansible
playbook из раздела «Новый релиз»: он обновляет migration и весь Compose stack
(Django, worker, Beat и bot) как одну поддерживаемую поставку. Не запускать
ручной `docker compose` и не развертывать backend и bot отдельными этапами.
После успешного playbook выполнить предусмотренный post-deploy smoke: проверить
HTTP/Compose/SHA по шагу 5 и создать только неплатёжный Crypto Pay invoice, если
операционные test credentials разрешают это. Не оплачивать счёт.

Для непроизводственного smoke использовать отдельные testnet token/secret и
`CRYPTOPAY_BASE_URL=https://testnet-pay.crypt.bot`. Создать один счёт для
локального тестового пользователя, зафиксировать только HTTP status,
`rub_amount`, `expires_at`, `reused` и наличие HTTPS URL, затем повторить запрос
для `reused=true`. Счёт не оплачивать; production smoke не заменяет testnet.

При rollback развернуть предыдущий совместимый SHA тем же Ansible playbook как
один whole-stack release: прежний bot скроет Crypto Pay-кнопки, а backend
вернётся вместе с ним. Additive migration, backend env и provider webhook
оставить: без Crypto Pay-кнопок они безвредны и не требуют ручного Compose или
component-level rollback. Не удалять и не откатывать реальные `Payment` или
`CryptoPaymentIntent` строки и не менять продукты. Merge и production deploy
требуют отдельных явных разрешений.

## VPN rollout

До включения VPN-продаж задать `VPN_SUBSCRIPTION_BASE_URL` и защищённый
`VPN_AGENT_TOKEN` вне Git. После отдельного release gate сначала развернуть и
проверить VPN node-agent и оба transport на ноде, затем backend/bot с неактивным
товаром `vpn_30d`. Создать `VPNInstance` неактивной, выполнить backfill, провести
smoke-check и активировать ноду вручную; только затем включить товар и выполнить
реальную smoke-покупку с импортом subscription URL в HAPP. Эти действия не
являются разрешением на merge или production deploy.

Для первого MVP rollout `VPNInstance.management_url` указывает на публичный
plaintext HTTP management proxy ноды. Host firewall отсутствует; bearer token
и route allowlist остаются. Риск перехвата token/profile payload принят
пользователем до deploy.
