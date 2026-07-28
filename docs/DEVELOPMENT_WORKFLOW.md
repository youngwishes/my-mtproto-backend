# Workflow разработки и выпуска

Этот процесс обязателен для каждой новой фичи. Для исследования, code review или
другой задачи без изменения продукта применяются только релевантные этапы;
деплоить отсутствие изменений не нужно.

## 0. Фиксация Scope Contract

До планирования и реализации главный агент фиксирует текущую версию Scope
Contract. Для продуктовой задачи она содержит утверждённые пользователем цель,
наблюдаемое поведение, BR/AC и non-goals. Для любой задачи в неё также входят
разрешённые компоненты, ожидаемые файлы, существенные ограничения и соразмерный
бюджет изменения.

Scope Contract является единственным источником обязательных требований для
всех ролей. Риски, идеи, defensive hardening и возможные edge cases не становятся
требованиями автоматически. Изменение пользовательского поведения, BR/AC,
non-goals, контракта или границы компонентов требует остановки работы и нового
явного подтверждения пользователя.

Перед каждой передачей работы главный агент формирует task packet:

- `scope_revision`;
- назначенные BR/AC и пункты плана;
- разрешённые и ожидаемые файлы;
- запрещённую соседнюю работу и релевантные non-goals;
- зависимости, бюджет и проверяемый критерий завершения.

Получивший пакет агент работает только внутри него. Если этого недостаточно, он
не меняет файлы и возвращает `scope_change_request` с минимальным обоснованным
расширением. Главный агент может уточнить технический бюджет или список файлов
внутри прежнего поведения и компонентов. Иное расширение подтверждает только
пользователь. Каждая revision неизменяема: после разрешённого изменения главный
агент повышает `scope_revision`, повторно передаёт contract затронутым ролям и
отменяет их старые task packets.

Каждое изменение выполняется в отдельной ветке `codex/<feature-slug>` и
доставляется Pull Request-ом в `main`. Агент может самостоятельно создавать
ветку, commit, push и PR, но не делает прямой push в `main` и не выполняет merge
без отдельного явного разрешения пользователя. Production deploy требует ещё
одного, нового явного разрешения непосредственно перед запуском playbook.

## 1. Подготовка

1. Прочитать постановку и профильные документы из `docs/`.
2. Проверить `git status --short`, текущую ветку и последние изменения. Не
   перезаписывать и не включать в commit чужие незавершённые изменения.
3. Обновить локальный `main` без переписывания истории и создать от него ветку
   `codex/<feature-slug>`. Если рабочее дерево грязное или `main` разошёлся с
   `origin/main`, сначала исследовать состояние и не терять чужие изменения.
4. Проверить доступность GitHub CLI командой `gh auth status`. Отсутствие `gh`
   или авторизации является блокером публикации PR и не разрешает fallback на
   прямой push в `main`.
5. Найти существующие сервисы, selectors, DTO, exceptions, factories и тестовые
   паттерны, которые можно переиспользовать.
6. Сверить постановку, критерии приёмки, затронутые контракты и риски с текущим
   Scope Contract. Не добавлять найденные риски в требования без
   `scope_change_request`.
7. Для рискованных изменений определить обратную совместимость миграций и
   стратегию отката до написания кода.

## 2. Реализация через TDD

1. Написать минимальный тест на один новый сценарий.
2. Запустить его и убедиться, что он падает по ожидаемой причине.
3. Реализовать минимальное изменение, необходимое для прохождения теста.
4. Запустить тест снова и получить зелёный результат.
5. Рефакторить только на зелёных тестах; повторять цикл для следующих сценариев.
6. Соблюдать service layer, dependency injection, selectors и остальные правила
   из `AGENTS.md`.
7. После каждого пункта сверять diff с task packet. Не изменять соседние файлы
   или поведение без нового назначения от главного агента.

## 3. Проверка и документация

1. Запустить релевантные тесты во время разработки, затем полный suite:

   ```bash
   make test
   ```

2. Проверить production Compose-конфигурацию:

   ```bash
   docker compose -f docker-compose.yml config --quiet
   ```

3. Выполнить доступные статические проверки проекта, если изменение затрагивает
   проверяемый ими код.
4. Просмотреть итоговый diff на соответствие Scope Contract и task packets,
   отсутствие секретов, случайных файлов, unrelated changes и превышения
   согласованного бюджета.
5. Обновить соответствующие docstrings и `docs/BUSINESS.md`, `ARCHITECTURE.md`,
   `CONTRACTS.md`, `MODELS.md` или `docs/apps/`. Если обновление не требуется,
   явно проверить это, а не пропускать этап автоматически.

## 4. Публикация Pull Request

После зелёных проверок агент самостоятельно:

1. Добавляет только относящиеся к фиче файлы.
2. Создаёт осмысленный commit в feature-ветке; commit в `main` запрещён.
3. Выполняет push feature-ветки и открывает Pull Request с base `main`.
4. В описании PR указывает `scope_revision`, scope, non-goals, связанные BR/AC
   при наличии, проверки, риски и влияние на deploy.
5. Сохраняет номер PR, URL и точный head SHA:

   ```bash
   FEATURE_BRANCH="$(git branch --show-current)"
   PR_BODY_FILE="<path-to-prepared-pr-body>"
   test "$FEATURE_BRANCH" != main
   gh auth status
   git push -u origin "$FEATURE_BRANCH"
   PR_URL="$(gh pr create --base main --head "$FEATURE_BRANCH" \
     --title "<PR title>" --body-file "$PR_BODY_FILE")"
   PR_NUMBER="$(gh pr view "$PR_URL" --json number --jq '.number')"
   PR_HEAD_SHA="$(gh pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid')"
   test "$PR_HEAD_SHA" = "$(git rev-parse HEAD)"
   ```

Если push отклонён, `main` изменился или PR нельзя создать, агент не переписывает
удалённую историю и не пушит напрямую в `main`: сначала исследует расхождение и
сообщает пользователю точный блокер.

## 5. Финальное ревью Pull Request

1. Главный агент передаёт новому `code-reviewer` номер PR и `PR_HEAD_SHA`.
2. Reviewer в read-only режиме читает метаданные, полный diff и checks через
   `gh pr view`, `gh pr diff` и `gh pr checks`, затем публикует один
   структурированный комментарий через `gh pr review --comment`.
3. Каждая находка классифицируется как `blocking_in_scope`,
   `scope_change_request` или `follow_up`. Для `blocking_in_scope` обязательна
   ссылка на BR/AC, non-goal, пункт плана или конкретную регрессию из diff.
4. Комментарий заканчивается точным вердиктом `VERDICT: approved` либо
   `VERDICT: changes_requested` и содержит проверенный head SHA.
   `changes_requested` разрешён только при наличии `blocking_in_scope`.
5. Главный агент проверяет классификацию. Implementer-у возвращаются только
   подтверждённые `blocking_in_scope`; остальные находки не становятся задачами
   текущего PR. После нового commit/push старый review считается устаревшим, а
   новый экземпляр reviewer-а проверяет новый head SHA.
6. Перед завершением главный агент подтверждает, что обязательные checks зелёные,
   SHA не изменился и последний review содержит `VERDICT: approved`:

   ```bash
   gh pr checks "$PR_NUMBER" --watch
   test "$(gh pr view "$PR_NUMBER" --json headRefOid --jq '.headRefOid')" = \
     "$PR_HEAD_SHA"
   ```

При завершении работы агент оставляет PR открытым и сообщает пользователю URL,
проверенный head SHA и результаты checks. Создание PR не разрешает его merge.

## 6. Merge и pre-deploy

Только после явного разрешения пользователя агент может выполнить merge
проверенного SHA:

```bash
gh pr merge "$PR_NUMBER" --squash --delete-branch \
  --match-head-commit "$PR_HEAD_SHA"
RELEASE_SHA="$(gh pr view "$PR_NUMBER" --json mergeCommit --jq '.mergeCommit.oid')"
git fetch origin main
test "$(git rev-parse origin/main)" = "$RELEASE_SHA"
```

После merge проверить playbook для опубликованного SHA:

```bash
ansible-playbook -i ansible/inventory/production.ini ansible/deploy.yml \
  --syntax-check -e deploy_revision="$RELEASE_SHA" \
  --private-key ~/.ssh/id_ed25519_deploy
```

При необходимости агент может до deploy собирать данные на production по SSH:

- адрес и пользователь берутся только из `ansible/inventory/production.ini`;
- предпочтителен доступ через Ansible inventory, например `ansible mtproto_keys`;
- допустима read-only диагностика: состояние сервисов, логи, текущий SHA,
  доступность диска и health checks;
- нельзя изменять файлы, БД, контейнеры, конфигурацию или состояние сервисов;
- нельзя выводить в ответ или commit секреты и содержимое production env-файлов.

После успешных проверок агент обязан остановиться и запросить явное разрешение,
указав `RELEASE_SHA`, результаты тестов и существенные риски. Без нового ответа
пользователя, явно разрешающего этот deploy, playbook не запускается.

## 7. Deploy и post-deploy

Только после явного разрешения пользователя выполнить:

```bash
ansible-playbook -i ansible/inventory/production.ini ansible/deploy.yml \
  -e deploy_revision="$RELEASE_SHA" \
  --private-key ~/.ssh/id_ed25519_deploy
```

Затем убедиться, что playbook завершился с `failed=0`, и проверить production
через inventory, без жёстко заданного IP:

```bash
curl --fail --silent --show-error https://beatvault.ru/ >/dev/null
ansible -i ansible/inventory/production.ini mtproto_keys \
  --private-key ~/.ssh/id_ed25519_deploy \
  -m ansible.builtin.shell \
  -a 'git -C /root/my-mtproto-backend rev-parse HEAD && cd /root/my-mtproto-backend && docker compose ps'
```

Сверить production SHA с `RELEASE_SHA`, состояние всех сервисов и smoke-check
изменённого пользовательского сценария. В итоговом отчёте указать commit,
результаты проверок и deploy.

При ошибке не выполнять импровизированные ручные исправления. Сохранить вывод,
проверить автоматический rollback playbook и согласовать дальнейшие действия.
Код и контейнеры можно вернуть на предыдущую версию, но уже применённые миграции
БД автоматически не откатываются.
