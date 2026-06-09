# Design: Move notification tasks from `vds` to `notifications`

**Date:** 2026-06-08

## Problem

`apps/vds/tasks.py` contains three tasks that are business-wise notifications to users, not VDS infrastructure operations. They are mixed in with tasks that manipulate VDS servers and keys, making the responsibility boundary unclear.

## Decision

Move the three notification-related tasks and their services to the `notifications` app. The `vds` app retains only tasks that deal with VDS infrastructure.

## What moves

### Service files

`vds/services/` → `notifications/services/`:

- `notify_before_removing_daily_service.py` — sends Telegram message to users whose key expires tomorrow
- `notify_before_removing_hour_before_service.py` — sends Telegram message to users whose key expires today
- `broadcast_proxy_links_service.py` — broadcasts proxy links to all active users (also extends `expired_date` by 3 days as compensation)

### Celery task functions

`vds/tasks.py` → `notifications/tasks.py`:

- `notify_before_removing_daily`
- `notify_before_removing_daily_hour_before`
- `broadcast_proxy_links_task`

## Changes to supporting files

| File | Change |
|---|---|
| `vds/services/__init__.py` | Remove imports and `__all__` entries for the 3 moved services |
| `notifications/services/__init__.py` | Add imports and `__all__` entries for the 3 moved services |
| `config/settings/celery.py` | Update beat schedule task paths for `notify_before_removing_daily` and `notify_before_removing_daily_hour_before` from `apps.vds.tasks.*` to `apps.notifications.tasks.*` |

## What does NOT change

- Service internals — `from apps.vds.selectors import ...` stays as-is (cross-app dependency is intentional and correct)
- `broadcast_proxy_links_task` is not in the Celery beat schedule (triggered manually), so no beat schedule entry needs updating for it

## Result

| App | Tasks after refactor |
|---|---|
| `vds` | `migrate_vds_keys_task`, `remove_user_keys_daily`, `add_key_to_another_vds_instances_task`, `remove_key_from_another_vds_instances_task` |
| `notifications` | `send_mailing_task`, `notify_before_removing_daily`, `notify_before_removing_daily_hour_before`, `broadcast_proxy_links_task` |
