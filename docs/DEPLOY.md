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

## VPN rollout

До включения VPN-продаж задать `VPN_SUBSCRIPTION_BASE_URL` и защищённый
`VPN_AGENT_TOKEN` вне Git. После отдельного release gate сначала развернуть и
проверить VPN node-agent и оба transport на ноде, затем backend/bot с неактивным
товаром `vpn_30d`. Создать `VPNInstance` неактивной, выполнить backfill, провести
smoke-check и активировать ноду вручную; только затем включить товар и выполнить
реальную smoke-покупку с импортом subscription URL в HAPP. Эти действия не
являются разрешением на merge или production deploy.
