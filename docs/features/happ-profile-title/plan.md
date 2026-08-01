# HApp Profile Title Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use
> `superpowers:subagent-driven-development` (recommended) or
> `superpowers:executing-plans` to implement this plan task-by-task. Steps use
> checkbox (`- [ ]`) syntax for tracking.

- **Status:** approved
- **Scope revision:** 1
- **Route:** small local feature; the root agent determined that no separate
  architecture decision or architecture review is required because the change
  adds one response header to an existing endpoint without changing models,
  services, components, or data flow.

**Goal:** Успешный ответ существующей публичной VPN subscription URL сообщает
HApp фиксированное отображаемое имя `mtprotokeys.ru`, не меняя URL или payload.

**Architecture:** `VPNSubscriptionView` добавляет стандартный HTTP-заголовок
`profile-title` непосредственно в уже сформированный `HttpResponse`. Существующий
happy-path API test продолжает проверять точный decoded payload и дополнительно
фиксирует новый header contract; отдельные настройки и новый слой логики не
добавляются.

**Tech Stack:** Python 3.13, Django 6, Django REST Framework APITestCase,
unittest assertions, Markdown API contracts.

## Global Constraints

- Единственный источник обязательных требований — approved
  `docs/features/happ-profile-title/business.md`, `scope_revision: 1`:
  BR-001, AC-001 и AC-002.
- Production-код изменяется только после RED: один новый assertion должен
  сначала упасть из-за отсутствующего `profile-title`, затем пройти после одной
  строки production-изменения.
- Значение заголовка фиксировано и посимвольно равно `mtprotokeys.ru`; не
  переносить его в settings, environment или admin.
- Не менять subscription URL, DNS, TLS, response body/payload,
  `subscription-userinfo`, VPN nodes, deploy или другие response headers.
- Бюджет: один новый test assertion, одна строка установки response header и
  компактное обновление существующего GET subscription contract.
- Разрешены только `src/apps/vpn/tests/test_subscription_view.py`,
  `src/apps/vpn/api/v1/views/subscription_views.py` и `docs/CONTRACTS.md`.
- `apps/music/` не читать и не изменять. Implementer не создаёт ветку, commit,
  push, PR, merge или deploy; эти gates остаются у главного оркестратора.

## File and Interface Map

- `src/apps/vpn/tests/test_subscription_view.py` — существующий happy-path test
  сохраняет точную проверку decoded profile payload и получает ровно один новый
  assertion `response["profile-title"] == "mtprotokeys.ru"`.
- `src/apps/vpn/api/v1/views/subscription_views.py` — существующий успешный
  `HttpResponse` получает ровно одну строку
  `response["profile-title"] = "mtprotokeys.ru"` перед возвратом.
- `docs/CONTRACTS.md` — раздел VPN кратко фиксирует публичный
  `GET /api/v1/vpn/subscriptions/<token>/`, успешный `text/plain` response и точный
  заголовок `profile-title: mtprotokeys.ru`, без изменения payload и URL.

## Dependency and Batch Graph

```text
HPT-B1 (one implementer): HPT-001 -> read-only batch review
    -> root integration verification
```

Параллельной работы нет: один атомарный пункт объединяет RED, минимальный GREEN
и синхронизацию контракта для одного endpoint.

---

### Task 1: HPT-001 — Зафиксировать название HApp-профиля в успешном subscription response

**Result:** `GET /api/v1/vpn/subscriptions/<token>/` для существующей подписки
возвращает `200 OK` с `profile-title: mtprotokeys.ru`; существующая точная
проверка decoded payload остаётся неизменной и продолжает проходить.

**Requirements:** BR-001; AC-001, AC-002.

**Dependencies:** approved `business.md`, `scope_revision: 1`; заключение root
agent об отсутствии архитектурного изменения; незавершённых code dependencies
нет.

**Files and ownership:**

- Modify/Test: `src/apps/vpn/tests/test_subscription_view.py` — только один
  header assertion внутри
  `test_active_subscription_returns_happ_profiles_without_bot_authentication`;
  существующие status, content-type, cache, security и payload assertions не
  менять.
- Modify: `src/apps/vpn/api/v1/views/subscription_views.py` — только одна строка
  установки фиксированного response header; service lookup, 404 flow, content
  type, cache/security headers и body не менять.
- Modify: `docs/CONTRACTS.md` — только компактное описание существующего
  публичного subscription GET contract и нового заголовка в разделе VPN;
  соседние endpoints не менять.

**Interfaces:**

- Consumes: существующий `VPNSubscriptionView.get(request, token) ->
  HttpResponse` и текущий Base64 `text/plain` payload.
- Produces: успешный HTTP response header
  `profile-title: mtprotokeys.ru`; сигнатуры Python и payload остаются прежними.

- [ ] **RED — добавить ровно один assertion.** После существующих header
  assertions в happy-path test добавить:

  ```python
  self.assertEqual(response["profile-title"], "mtprotokeys.ru")
  ```

  Существующий `b64decode(response.content)...` assertion не менять: он является
  regression-проверкой AC-002.

- [ ] **Запустить RED и подтвердить ожидаемую причину.** Из корня репозитория:

  ```bash
  make test ARGS="apps.vpn.tests.test_subscription_view.TestVPNSubscriptionView.test_active_subscription_returns_happ_profiles_without_bot_authentication"
  ```

  Ожидаемый результат до production-изменения: FAIL/ERROR на чтении
  отсутствующего response header `profile-title`; payload assertion не должен
  быть причиной падения.

- [ ] **GREEN — добавить минимальное production-изменение.** В
  `VPNSubscriptionView.get`, рядом с существующими response headers и до
  `return response`, добавить ровно:

  ```python
  response["profile-title"] = "mtprotokeys.ru"
  ```

  Не вводить constant, setting, helper или условную ветку.

- [ ] **Подтвердить targeted GREEN.** Повторить ту же команду и получить PASS;
  существующая точная проверка decoded VLESS/Hysteria payload должна пройти без
  изменения expected value.

- [ ] **Синхронизировать контракт.** В VPN-разделе `docs/CONTRACTS.md` добавить
  короткий subsection `GET /api/v1/vpn/subscriptions/<token>/`: endpoint публичный,
  успешный ответ имеет `200 OK`, `Content-Type: text/plain` и
  `profile-title: mtprotokeys.ru`; добавление заголовка не меняет существующую
  subscription URL или Base64 payload. Не документировать новые настройки,
  body fields или соседние изменения.

- [ ] **Выполнить проверку партии.** Из корня репозитория:

  ```bash
  make test ARGS="apps.vpn.tests.test_subscription_view"
  make test
  docker compose -f docker-compose.yml config --quiet
  git diff --check
  ```

  Критерий завершения: targeted и полный suites зелёные, Compose config валиден,
  `git diff --check` успешен, diff содержит только три разрешённых файла и
  укладывается в бюджет одного assertion, одной строки header и компактной
  документации; URL, payload и все non-goals не изменены.

## Task Packet HPT-B1

- **scope_revision:** 1.
- **Plan items:** HPT-001.
- **Requirements:** BR-001; AC-001, AC-002.
- **Allowed/expected files:**
  `src/apps/vpn/tests/test_subscription_view.py`,
  `src/apps/vpn/api/v1/views/subscription_views.py`, `docs/CONTRACTS.md`.
- **Forbidden adjacent work:** любые другие файлы; рефакторинг view/service;
  constants/settings; изменение URL, DNS/TLS, payload,
  `subscription-userinfo`, nodes, deploy и конфигурируемость title.
- **Dependencies:** approved business artifact и root architectural
  determination; HPT-001 выполняется последовательно RED → GREEN → docs →
  verification.
- **Budget:** один test assertion, одна production header line, одно компактное
  contract addition; один implementer, один plan item.
- **Completion criterion:** точный header contract и неизменный payload
  подтверждены тестом, документация согласована, все команды проверки успешны,
  изменения вне разрешённых файлов отсутствуют.
