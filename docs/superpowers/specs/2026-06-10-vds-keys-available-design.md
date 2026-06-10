# VDSInstance.is_keys_available — дизайн

**Дата:** 2026-06-10

## Контекст

Нужно добавить булевое поле `is_keys_available` на `VDSInstance`, которое разрешает или запрещает направлять новые прокси-ссылки на этот сервер. Поле позволяет выводить сервер из ротации без его полного отключения (`is_active=False`).

## Архитектурный контекст

Каждый `VDSInstance` имеет собственный сабдомен (`node_number.beatvault.ru`). Прокси-ссылка пользователя жёстко привязана к конкретному серверу через `MTPRotoKey.node_number`. Секрет (secret) при выдаче или перевыпуске реплицируется на **все** остальные VDS, поэтому один и тот же секрет работает на любом сервере. Выбор VDS определяет только то, на какой сабдомен ведёт ссылка.

### Существующий скрытый баг

`UpdateKeyInfraService` при перевыпуске ключа запускает `add_key_to_another_vds_instances_task`, которая делает POST на другие серверы. Но пользователь там уже существует (был реплицирован при первичной выдаче), поэтому POST падает и уходит уведомление администратору. Это задача исправляет баг как часть работы.

## Изменения

### 1. Модель `VDSInstance`

Добавить поле:
```python
is_keys_available = models.BooleanField("выпуск ключей доступен", default=True)
```

`default=True` — все существующие серверы продолжают работать без ручного изменения данных.

### 2. `VDSQuerySet.order_by_population()`

Добавить фильтр по новому полю:
```python
def order_by_population(self):
    return (
        self.active()
        .filter(is_keys_available=True)
        .annotate(keys_count_annotation=Count("keys"))
        .order_by("keys_count_annotation")
    )
```

Это автоматически применяется везде, где используется `get_least_populated_vds()`: выдача нового ключа (`IssueKeyService`), а также выбор целевого сервера при перевыпуске.

### 3. Новый `UpdateKeyOnAnotherVdsInfraService`

Новый файл `apps/vds/services/update_key_on_another_vds_infra_service.py`. Аналог `AddKeyToAnotherVdsInfraService`, но делает PATCH (обновить секрет) вместо POST. Нотификация администратора сохраняется при ошибке.

```
apps/vds/services/update_key_on_another_vds_infra_service.py
```

### 4. Новый Celery-таск `update_key_on_another_vds_instances_task`

В `tasks.py` добавить таск-обёртку над новым сервисом — по образцу `add_key_to_another_vds_instances_task`.

### 5. `UpdateKeyInfraService`

Два изменения:
- Принимает явный параметр `server: VDSInstance` вместо `old_key.vds` — это позволяет направить PATCH на нужный сервер (может отличаться от сервера старого ключа при миграции).
- Переключается на `update_key_on_another_vds_instances_task` (PATCH-репликация) вместо `add_key_to_another_vds_instances_task` (POST).

### 6. `UpdateKeyService`

Логика выбора VDS и ветвление:

```python
server = get_least_populated_vds()  # уже фильтрует is_keys_available=True
response = infra(username=username, old_key=key, server=server)

key.token = response.key
key.tls_domain = response.tls_domain
key.last_update = timezone.now()
key.was_deleted = False
key.is_active = True

update_fields = ["token", "tls_domain", "node_number", "last_update", "was_deleted", "is_active"]

if server != key.vds:
    key.vds = server
    key.node_number = server.name
    update_fields += ["vds"]

key.save(update_fields=update_fields)
```

`node_number` обновляется всегда (уже был в `update_fields`). `vds` — только при смене сервера.

## Тестирование

Тесты пишутся до реализации (TDD). Покрываемые сценарии:

- Выдача нового ключа выбирает только VDS с `is_keys_available=True`
- Перевыпуск ключа, когда текущий VDS имеет `is_keys_available=True` → остаётся на том же сервере
- Перевыпуск ключа, когда текущий VDS имеет `is_keys_available=False` → мигрирует на новый VDS, `node_number` и `vds` обновляются
- `UpdateKeyOnAnotherVdsInfraService` делает PATCH, а не POST
- При ошибке репликации уведомляется администратор

Используются `APITestCase` + `factory_boy` + `responses` для мока VDS HTTP-вызовов. Telegram-нотификации патчатся через `apps.core.bot.TelegramBot`.

## Что не меняется

- `AddNewKeyInfraService` — POST-репликация для новых ключей остаётся без изменений
- `FirstFreeLinkService`, `GetReferralVDSLinkService` — не меняются, фильтр применяется внутри `get_least_populated_vds()`
- `ExtendKeyService` — продление срока подписки, VDS не затрагивает
