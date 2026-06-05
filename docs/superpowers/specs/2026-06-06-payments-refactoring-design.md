# Рефакторинг apps/payments/

## Цель

Привести приложение payments в соответствие с SOLID, DRY и DDD: разделить ответственности сервиса, ввести DTOs, доменные исключения и инъекцию зависимостей.

## Что меняем

### 1. Разделение CreatePaymentService (SRP)

**Было:** один сервис совмещает продление ключа, выдачу нового и Telegram-нотификацию.

**Стало:** три сервиса с чёткими границами.

| Сервис | Ответственность |
|--------|----------------|
| `CreatePaymentService` | Оркестратор: принимает DTO, решает extend/issue, создаёт `Payment`, делегирует нотификацию |
| `ExtendKeyService` | Продлевает существующий ключ на `SUBSCRIPTION_PERIOD_DAYS`, отвязывает старые платежи |
| `NotifyPaymentService` | Отправляет пользователю прокси-ссылку через `TelegramBot` |

Зависимости инъецируются через поля dataclass:

```python
@final
@dataclass(kw_only=True, slots=True, frozen=True)
class CreatePaymentService:
    extend_key_service: ExtendKeyService
    notify_service: NotifyPaymentService

    @log_service_error
    def __call__(self, *, payment: CreatePaymentIn) -> None:
        user = get_user_by_username(username=payment.username)  # selector
        if user is None:
            raise BadPaymentData(telegram_id=payment.username)

        active_key = get_active_key(user=user)  # selector

        if active_key:
            self.extend_key_service(key=active_key)
        else:
            active_key = get_issue_key_service()(user=user, expired_date=...)

        Payment.objects.create(
            user=user, key=active_key,
            charge_id=payment.charge_id, provider=payment.provider,
        )
        self.notify_service(user=user, key=active_key)
```

Фабрика собирает граф:

```python
def get_create_payment_service() -> CreatePaymentService:
    return CreatePaymentService(
        extend_key_service=get_extend_key_service(),
        notify_service=get_notify_payment_service(),
    )
```

### 2. Константа SUBSCRIPTION_PERIOD_DAYS (DRY)

Новый файл `config/settings/payments.py`:

```python
SUBSCRIPTION_PERIOD_DAYS = 30
```

Импортируется в `config/settings/base.py` через `from .payments import *`.

Заменяет хардкод `timedelta(days=30)` в `ExtendKeyService` и вызовах `IssueKeyService`.

### 3. BaseServiceDTO + CreatePaymentIn (DTOs)

Новый класс в `apps/core/dtos.py`:

```python
from __future__ import annotations
from dataclasses import asdict, dataclass

@dataclass(kw_only=True, frozen=True, slots=True)
class BaseServiceDTO:
    def asdict(self) -> dict:
        return asdict(self)
```

DTO для payments в `services/dtos/create_payment_dto.py`:

```python
@dataclass(kw_only=True, frozen=True, slots=True)
class CreatePaymentIn(BaseServiceDTO):
    username: str
    charge_id: str
    provider: str
```

Вью создаёт DTO из validated_data:

```python
service = get_create_payment_service()
service(payment=CreatePaymentIn(**serializer.validated_data))
```

### 4. Селекторы

ORM-запросы выносятся в `selectors.py` — сервисы не содержат инлайн-фильтров.

`apps/vds/selectors.py`:

```python
def get_active_key(*, user: SystemUser) -> MTPRotoKey | None:
    """Активный (не удалённый, не истёкший) ключ пользователя."""
    return MTPRotoKey.objects.filter(
        user=user, was_deleted=False, expired_date__gt=now(),
    ).first()
```

`apps/users/selectors.py`:

```python
def get_user_by_username(*, username: str) -> SystemUser | None:
    """Находит пользователя по Telegram ID (хранится в username)."""
    return SystemUser.objects.filter(username=username).first()
```

### 5. Доменные исключения

Новый файл `apps/payments/exceptions.py`:

```python
from apps.core.service import BaseServiceError

class BadPaymentData(BaseServiceError):
    """Некорректные данные платежа"""

class ProductNotFound(BaseServiceError):
    """Продукт не найден"""
```

- `BadPaymentData` — бросается в `CreatePaymentService`, если пользователь не найден по username.
- `ProductNotFound` — бросается в `ProductAPIView`, если нет активного продукта.

### 6. Удаление легаси

Удалить пустой файл `src/apps/payments/views.py`.

### 7. Документация

Docstring на каждом сервисе — что делает, какие ошибки бросает:

```python
@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ExtendKeyService:
    """Продлевает активный ключ на SUBSCRIPTION_PERIOD_DAYS дней.

    Отвязывает предыдущие платежи от ключа (key=NULL),
    чтобы новый Payment стал единственным владельцем связи.

    Raises:
        Нет собственных исключений.
    """
```

## Итоговая структура файлов

```
apps/payments/
├── __init__.py
├── apps.py                              # ready() импортирует services
├── models.py
├── enums.py
├── exceptions.py                        # NEW: BadPaymentData, ProductNotFound
├── admin.py
├── api/
│   ├── urls.py
│   └── v1/
│       ├── urls.py
│       ├── serializers/
│       │   ├── __init__.py
│       │   ├── create_payment_serializer.py
│       │   └── get_product_serializer.py
│       └── views/
│           ├── __init__.py
│           ├── create_payment_view.py   # UPDATED: uses DTO
│           └── get_product_view.py      # UPDATED: raises ProductNotFound
├── services/
│   ├── __init__.py                      # UPDATED: реэкспорт всех фабрик
│   ├── create_payment_service.py        # UPDATED: оркестратор с DI
│   ├── extend_key_service.py            # NEW
│   ├── notify_payment_service.py        # NEW
│   └── dtos/
│       ├── __init__.py                  # NEW
│       └── create_payment_dto.py        # NEW: CreatePaymentIn
└── tests/
    ├── factories.py
    ├── test_create_payment_service.py   # UPDATED: адаптация под новую структуру
    ├── test_extend_key_service.py       # NEW
    ├── test_notify_payment_service.py   # NEW
    └── test_views/
        ├── test_create_payment_view.py
        └── test_get_product_view.py

apps/vds/
├── selectors.py                         # NEW: get_active_key()
└── ...

apps/users/
├── selectors.py                         # NEW: get_user_by_username()
└── ...

apps/core/
├── dtos.py                              # NEW: BaseServiceDTO
└── ...
```

## Новые файлы (за пределами payments)

| Файл | Что |
|------|-----|
| `apps/core/dtos.py` | `BaseServiceDTO` с `asdict()` |
| `apps/vds/selectors.py` | `get_active_key()` — активный ключ пользователя |
| `apps/users/selectors.py` | `get_user_by_username()` — поиск пользователя по Telegram ID |
| `config/settings/payments.py` | `SUBSCRIPTION_PERIOD_DAYS = 30` |

## Тесты

- `test_extend_key_service.py` — продление даты, отвязка старых платежей
- `test_notify_payment_service.py` — вызов TelegramBot с правильными аргументами
- `test_create_payment_service.py` — обновить: мокать инъецированные сервисы вместо приватных методов; проверить `BadPaymentData` при несуществующем username
- `test_get_product_view.py` — добавить кейс: `ProductNotFound` при пустой таблице

## Что НЕ меняем

- Модели (`Product`, `Payment`) — без изменений
- Сериализаторы — контракт тот же
- URL-маршруты — без изменений
- `IssueKeyService` (apps/vds) — вызывается как раньше, через фабрику
