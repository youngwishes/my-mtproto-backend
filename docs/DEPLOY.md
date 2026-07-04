# Релиз через Ansible

Все команды выполняются из корня репозитория.

## Однократная подготовка

```bash
cp ansible/inventory/production.ini.example ansible/inventory/production.ini
cp ansible/group_vars/beatvault.yml.example ansible/group_vars/beatvault.yml
```

Проверь адрес сервера и остальные значения в созданных файлах. Они содержат
production-настройки и не добавляются в Git.

Проверь доступ к серверу:

```bash
ansible -i ansible/inventory/production.ini beatvault -m ansible.builtin.ping \
  --private-key ~/.ssh/id_ed25519_deploy
```

## Новый релиз

1. Убедись, что рабочее дерево содержит только изменения релиза, и запусти тесты:

   ```bash
   git status --short
   make test
   docker compose -f docker-compose.yml config --quiet
   ```

2. Создай commit и отправь его в `origin/main`:

   ```bash
   git add <files>
   git commit -m "Описание релиза"
   git push origin main
   ```

3. Сохрани полный SHA опубликованного commit и проверь playbook:

   ```bash
   RELEASE_SHA="$(git rev-parse HEAD)"
   test "$(git rev-parse origin/main)" = "$RELEASE_SHA"
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
   ansible -i ansible/inventory/production.ini beatvault \
     --private-key ~/.ssh/id_ed25519_deploy \
     -m ansible.builtin.shell \
     -a 'git -C /root/my-mtproto-backend rev-parse HEAD && cd /root/my-mtproto-backend && docker compose ps'
   ```

Playbook сам запускает миграции через entrypoint Django, проверяет HTTP-ответ и
состояние всех Compose-сервисов. При ошибке он возвращает предыдущий код и
контейнеры. Уже применённые миграции БД автоматически не откатываются; перед
ручным откатом проверь их совместимость и состояние backup в Litestream.
