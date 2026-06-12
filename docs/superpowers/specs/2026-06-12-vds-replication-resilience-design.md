# VDS Replication Resilience — Design Spec

**Date:** 2026-06-12
**Status:** Approved

## Problem

Key replication to secondary VDS servers fails silently when a server is temporarily unavailable.
Currently the system only sends an admin notification — no retry happens, and the key is never
replicated to the failed server even after it recovers. This leaves users with broken proxy links
for that server.

## Goals

- Automatically recover from transient failures (server down for minutes)
- Automatically recover from extended outages (server down for hours/days)
- Eliminate notification noise during retry window
- Reuse existing `sync_keys_to_vds_task` infrastructure for recovery

## Architecture

Three-layer protection:

```
Replication failure
  → Celery retry (60s → 240s → 960s)
      → success: done
      → all retries exhausted: is_healthy=False + admin notification
          → check_vds_health_task (every 5 min)
              → server responds: is_healthy=True + sync_keys_to_vds_task
                  → all active keys synced to recovered server
```

## Data Model Changes

### `VDSInstance` — new field

```python
is_healthy = models.BooleanField("сервер здоров", default=True)
```

**Semantics:**
- `True` — server is operating normally (default)
- `False` — all replication retries exhausted; health-check is monitoring

**Distinction from `is_active`:**
- `is_active=False` — server intentionally disabled by admin; excluded from replication entirely
- `is_healthy=False` — server is active but temporarily unreachable; will auto-recover

New migration required.

### New selector (`selectors.py`)

```python
def get_unhealthy_vds_instances() -> QuerySet[VDSInstance]:
    """Активные VDS-серверы, помеченные как нездоровые."""
    return VDSInstance.objects.active().filter(is_healthy=False)
```

### Admin

`is_healthy` added to `VDSInstanceAdmin.list_display` and `list_editable`.

## Tasks

### Refactored: `add_key_to_another_vds_instances_task`

Instead of calling `AddKeyToAnotherVdsInfraService` (which loops internally), now dispatches
one per-server task per server:

```python
@shared_task
def add_key_to_another_vds_instances_task(exclude: int, username: str, secret: str) -> None:
    servers = get_other_active_vds_instances(exclude_pk=exclude)
    for server in servers:
        replicate_key_add_to_server_task.delay(server.pk, username, secret)
```

Same refactor for `update_key_on_another_vds_instances_task` → dispatches
`replicate_key_update_to_server_task`.

### New: `replicate_key_add_to_server_task`

```python
@shared_task(bind=True, max_retries=3)
def replicate_key_add_to_server_task(self, server_id: int, username: str, secret: str) -> None:
    ...
```

- Calls `ReplicateKeyAddToServerInfraService`
- On exception: `self.retry(countdown=60 * 4 ** self.request.retries)`
  - Retry 1: 60s, Retry 2: 240s, Retry 3: 960s (~16 min)
- On `MaxRetriesExceededError`: marks `is_healthy=False`, sends admin notification (once)

### New: `replicate_key_update_to_server_task`

Same structure as above, calls `ReplicateKeyUpdateToServerInfraService`.

### New: `check_vds_health_task`

```python
@shared_task
def check_vds_health_task() -> None:
    ...
```

- Queries `get_unhealthy_vds_instances()`
- For each: calls `VDSHealthCheckInfraService`
- On success: sets `is_healthy=True`, fires `sync_keys_to_vds_task.delay(instance.pk)`
- On failure: no action, no notification (waits for next 5-min cycle)

Added to `CELERY_BEAT_SCHEDULE`:
```python
"check-vds-health": {
    "task": "apps.vds.tasks.check_vds_health_task",
    "schedule": crontab(minute="*/5"),
},
```

## Services

### Removed

- `AddKeyToAnotherVdsInfraService` — logic moved to task-level dispatch
- `UpdateKeyOnAnotherVdsInfraService` — same

### New: `ReplicateKeyAddToServerInfraService`

```python
@final
@dataclass(kw_only=True, slots=True, frozen=True)
class ReplicateKeyAddToServerInfraService:
    def __call__(self, *, server_id: int, username: str, secret: str) -> None:
        ...
```

- Fetches `VDSInstance` by `server_id`
- POST `/api/users`; if 409 (already exists) — returns silently
- Raises on any other exception (task handles retry)

### New: `ReplicateKeyUpdateToServerInfraService`

Same structure. PATCH `/api/users`; if 404 — falls back to POST.

### New: `VDSHealthCheckInfraService`

```python
@final
@dataclass(kw_only=True, slots=True, frozen=True)
class VDSHealthCheckInfraService:
    def __call__(self, *, instance_id: int) -> bool:
        ...
```

- GET `server.internal_url` with 5s timeout
- Returns `True` if any HTTP response received (even 4xx)
- Returns `False` on `ConnectionError` / timeout

## Error Handling Summary

| Scenario | Behaviour |
|---|---|
| Replication fails, server recovers within ~18 min | Silent retry, key delivered |
| Replication fails, server down >18 min | `is_healthy=False` + one admin notification |
| Server recovers after extended outage | Health-check detects → `sync_keys_to_vds_task` |
| User updates key while server is down | `sync_keys_to_vds_task` reads current `MTPRotoKey.token` — no stale data |
| Health-check fires, server still down | No action, no notification noise |

## Testing

- Per-server retry tasks: mock the infra service to raise, assert `self.retry` called with correct
  countdown; assert `is_healthy=False` set after `MaxRetriesExceededError`
- `check_vds_health_task`: mock `VDSHealthCheckInfraService` return values; assert
  `sync_keys_to_vds_task` fired only on `True`; assert `is_healthy` updated correctly
- `VDSHealthCheckInfraService`: use `responses` library to simulate connection error vs. 200

Test files:
- `apps/vds/tests/test_tasks/test_replicate_key_add_to_server_task.py`
- `apps/vds/tests/test_tasks/test_replicate_key_update_to_server_task.py`
- `apps/vds/tests/test_tasks/test_check_vds_health_task.py`
- `apps/vds/tests/test_services/test_replicate_key_add_to_server_infra_service.py`
- `apps/vds/tests/test_services/test_replicate_key_update_to_server_infra_service.py`
- `apps/vds/tests/test_services/test_vds_health_check_infra_service.py`
