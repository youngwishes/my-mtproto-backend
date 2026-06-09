---
date: 2026-06-08
topic: Refactor remove_user_keys_daily task
status: approved
---

# Design: Refactor `remove_user_keys_daily`

## Goal

Extract all inline logic from the `remove_user_keys_daily` Celery task into a dedicated service, following the same pattern as `migrate_vds_keys_task` / `MigrateVdsKeysInfraService`.

## New file: `src/apps/vds/services/remove_expired_keys_daily_service.py`

Frozen dataclass `RemoveExpiredKeysDailyService` with a single `__call__()`:

1. Get expired keys via `get_keys_expired_up_to_date(date=timezone.now().date())`
2. Early return if queryset is empty
3. Loop over `get_all_active_vds_instances()`, call `RemoveUserKeyInfraService` for each server
4. `queryset.update(is_active=False, was_deleted=True)`
5. Collect usernames, send Telegram notification per user (with `time.sleep(1)` between sends)
6. On notification error — send admin alert via `send_telegram_message`

Factory function `get_remove_expired_keys_daily_service()` at module level.

## Updated task (`tasks.py`)

```python
@shared_task
def remove_user_keys_daily():
    from apps.vds.services import get_remove_expired_keys_daily_service
    get_remove_expired_keys_daily_service()()
```

All inline code removed. Task becomes a thin Celery entry point.

## Exports (`services/__init__.py`)

Add `RemoveExpiredKeysDailyService` and `get_remove_expired_keys_daily_service` to imports and `__all__`.

## Tests

### `test_tasks/test_remove_user_task.py`

Replace all existing cases with a single `test_delegates_to_service` — mirrors `test_migrate_vds_keys_task.py`. Verifies side effects (HTTP DELETE called, key marked inactive).

### `test_services/test_remove_expired_keys_daily_service.py` (new)

Move and adapt the existing four cases to test the service directly:

- **case1**: no expired keys → service exits early, VDS not called
- **case2**: key expires in the future → service exits early, VDS not called
- **case3**: key expired today → VDS DELETE called once, user notified, second call is no-op
- **case4**: key expired yesterday → same as case3
