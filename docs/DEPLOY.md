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

## Fortune wheel: production-конфигурация

До первого релиза добавь в защищённый `bot/.env` публичный URL:

```dotenv
FORTUNE_WHEEL_URL=https://dash.mtprotokeys.com/fortune-wheel/
```

Backend использует существующий `BOT_TOKEN` для проверки Telegram Mini App
`initData`. Необязательный
`FORTUNE_WHEEL_INIT_DATA_MAX_AGE_SECONDS=3600` задаётся в корневом `.env`.
Значения токенов не переносятся во frontend.

После успешного deploy настрой у этого же бота в @BotFather Main Mini App с URL
`https://dash.mtprotokeys.com/fortune-wheel/`. Это создаёт кнопку открытия в
профиле; кнопка на экране `🍏 Мои яблоки` использует `FORTUNE_WHEEL_URL`.

Production smoke дополняется проверкой страницы и ручным запуском из обеих
точек входа. У тестового зарегистрированного пользователя проверь одно
вращение, сохранённый последний приз, таймер и появление строки в read-only
Django Admin:

```bash
curl --fail --silent --show-error \
  https://dash.mtprotokeys.com/fortune-wheel/ >/dev/null
```

## VPN: production-конфигурация

VPN использует `VPN_SUBSCRIPTION_BASE_URL` и защищённый `VPN_AGENT_TOKEN` вне
Git. До включения отдельного прокси base URL — `https://dash.mtprotokeys.com`.
Обычный релиз не повторяет первоначальный
rollout node-agent, transport, `VPNInstance` и товара `vpn_30d`.

В текущем MVP `VPNInstance.management_url` указывает на публичный plaintext HTTP
management proxy ноды. Host firewall отсутствует; bearer token и route allowlist
остаются. Риск перехвата token/profile payload принят пользователем.

Application rollback на предыдущий SHA не восстанавливает уже ротированные
subscription token, VLESS UUID и Hysteria secret. После отката асинхронная
доставка должна довести до нод актуальные credentials из БД; вручную возвращать
старые credentials нельзя.

### Отдельный HTTPS-прокси подписок

Proxy устанавливается на выделенный Ubuntu VPS. DNS A-запись
`api.meow-meow-fast.site` должна указывать на `212.192.4.192`; входящие TCP 80
и 443 должны быть доступны. На сервере не должно быть другого web-сервера:
playbook отключает стандартный сайт Nginx и управляет отдельным конфигом.
Порт 80 нужен также для продления сертификата Let's Encrypt. Certbot
регистрируется без email; за сроком сертификата нужно следить внешним мониторингом.

До публикации проверь реальный Nginx с тестовым TLS upstream в Docker:

```bash
docker pull nginx:alpine
python3 -m unittest scripts.tests.test_vpn_subscription_proxy
```

К прокси применяются те же требования к merged PR, точному `RELEASE_SHA` и
отдельному разрешению на production deploy из раздела «Новый релиз». Запускай
playbook из checkout этого SHA. Сначала выполни только syntax check:

```bash
ansible-playbook -i ansible/inventory/vpn-subscription-proxy.ini \
  ansible/vpn-subscription-proxy.yml --syntax-check \
  -e deploy_revision="$RELEASE_SHA" --private-key ~/.ssh/id_ed25519_deploy
```

После отдельного разрешения на установку прокси:

```bash
ansible-playbook -i ansible/inventory/vpn-subscription-proxy.ini \
  ansible/vpn-subscription-proxy.yml -e deploy_revision="$RELEASE_SHA" \
  --private-key ~/.ssh/id_ed25519_deploy
```

Playbook выпускает сертификат через HTTP webroot, устанавливает HTTPS-конфиг,
включает `certbot.timer` и reload Nginx после продления. Повторный запуск
сохраняет существующий сертификат. Он не меняет backend-настройки.

Проверь `nginx -t`, таймер, пробное продление и внешний HTTPS. Токен ниже
вымышленный; ожидаются `404` для обоих HTTPS-запросов и `301` на тот же путь
нового HTTPS-домена для HTTP:

```bash
ansible -i ansible/inventory/vpn-subscription-proxy.ini vpn_subscription_proxy \
  --private-key ~/.ssh/id_ed25519_deploy -m ansible.builtin.command -a 'nginx -t'
ansible -i ansible/inventory/vpn-subscription-proxy.ini vpn_subscription_proxy \
  --private-key ~/.ssh/id_ed25519_deploy -m ansible.builtin.command \
  -a 'systemctl is-active certbot.timer'
ansible -i ansible/inventory/vpn-subscription-proxy.ini vpn_subscription_proxy \
  --private-key ~/.ssh/id_ed25519_deploy -m ansible.builtin.command \
  -a 'certbot renew --dry-run --run-deploy-hooks'
curl --silent --show-error -o /dev/null -w '%{http_code}\n' \
  https://api.meow-meow-fast.site/api/v1/vpn/subscriptions/proxy-connectivity-check/
curl --silent --show-error -o /dev/null -w '%{http_code}\n' \
  https://api.meow-meow-fast.site/admin/
curl --silent --show-error -D - -o /dev/null \
  http://api.meow-meow-fast.site/api/v1/vpn/subscriptions/proxy-connectivity-check/
```

Проверка с вымышленным token не доказывает выдачу рабочей подписки. В HAPP
тестового пользователя замени только домен действующей ссылки и проверь
обновление без включённого VPN из проблемной сети. Не выводи действующую
ссылку или содержимое подписки в логи, PR или командную строку.

Только после этой проверки запроси отдельное разрешение на переключение
backend. В рамках одобренного release обнови единственную настройку и затем
выполни стандартный deploy `ansible/deploy.yml` с тем же `RELEASE_SHA`:

```bash
ansible -i ansible/inventory/production.ini mtproto_keys \
  --private-key ~/.ssh/id_ed25519_deploy -m ansible.builtin.lineinfile \
  -a 'path=/root/my-mtproto-backend/.env regexp=^VPN_SUBSCRIPTION_BASE_URL= line=VPN_SUBSCRIPTION_BASE_URL=https://api.meow-meow-fast.site owner=root group=root mode=0600'
```

В боте открой «VPN → Моя подписка»: URL должен начинаться с нового домена,
а token оставаться прежним. Пользователям со старой ссылкой нужно заменить
её в HAPP ссылкой из бота. Они также могут нажать «Перевыпустить ссылку»:
результат использует новый домен, но при этом ротируются token и credentials,
поэтому новую ссылку нужно импортировать на всех их устройствах.

Rollback переключения: тем же модулем верни строку
`VPN_SUBSCRIPTION_BASE_URL=https://dash.mtprotokeys.com` и выполни одобренный
стандартный release. Автоматический rollback кода в `deploy.yml` не откатывает
`.env`; при неудаче переключения настройку нужно восстановить отдельно.
После выдачи новых ссылок сохраняй прокси работающим: возврат настройки в боте
не меняет уже импортированные адреса. Для отката конфига прокси используй
backup, созданный Ansible рядом с конфигом, затем `nginx -t` и reload.
