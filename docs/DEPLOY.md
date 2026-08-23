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

До release разрешена только read-only диагностика production через хост из
Ansible inventory: SHA, состояние сервисов, логи, health checks и свободное
место. Не изменяй файлы, БД, контейнеры или конфигурацию и не выводи секреты.

## Новый релиз

1. Убедись, что для точного PR head зелёные repository gates из
   [DEVELOPMENT_WORKFLOW.md](DEVELOPMENT_WORKFLOW.md#5-проверка), а локальный
   checkout не содержит незапланированных изменений.

2. Убедись, что Pull Request одобрен и merged в `main`. Прямой push релиза в
   `main` запрещён.
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

## VPN: production-конфигурация

VPN использует `VPN_SUBSCRIPTION_BASE_URL=https://dash.mtprotokeys.com` и
защищённый `VPN_AGENT_TOKEN` вне Git. Обычный релиз не повторяет первоначальный
rollout node-agent, transport, `VPNInstance` и товара `vpn_30d`.

В текущем MVP `VPNInstance.management_url` указывает на публичный plaintext HTTP
management proxy ноды. Host firewall отсутствует; bearer token и route allowlist
остаются. Риск перехвата token/profile payload принят пользователем.

Application rollback на предыдущий SHA не восстанавливает уже ротированные
subscription token, VLESS UUID и Hysteria secret. После отката асинхронная
доставка должна довести до нод актуальные credentials из БД; вручную возвращать
старые credentials нельзя.
