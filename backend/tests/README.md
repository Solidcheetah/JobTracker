# Backend tests

```bash
cd backend
uv run pytest              # whole suite
uv run pytest -v           # per-test names
uv run pytest tests/test_application_filtering.py
uv run pytest -k ownership
```

No Postgres or Redis required — tests use in-memory SQLite, and Redis calls are
monkeypatched. The suite runs in about 4 seconds.

## Layout

| File | Covers |
| --- | --- |
| `test_utils.py` | JWT encode/decode, expiry, tampering, unique `jti` |
| `test_auth_dependencies.py` | `get_current_user`: valid, missing, expired, revoked, malformed |
| `test_user_service.py` | Registration, password hashing/salting, login |
| `test_user_routes.py` | `/user/register`, `/login`, `/logout` |
| `test_application_service.py` | Create/read/update/delete, ownership, status history |
| `test_application_filtering.py` | Status/search/date filters, pagination, HTTP binding |
| `test_application_stats.py` | Stats aggregation, status history, `/recent` |
| `test_application_routes.py` | `/application` endpoints, validation, auth gating |

## What the fixtures do

`conftest.py` provides a fresh in-memory database per test, two users (`user`
and `other_user`) for cross-tenant checks, service instances bound to each, and
a `make_application` factory that inserts rows directly.

Two HTTP clients:

- `client` — authenticated as `user`, with `get_db` / `get_session` /
  `get_current_user` overridden.
- `anon_client` — no authenticated user, for 401 paths.

## Deliberate gaps

**Row-level security is not exercised.** The `application_owner_isolation` policy
is a Postgres feature and is inert on SQLite. Ownership tests therefore assert on
the service-layer checks, which is the layer that behaves identically on both.
Verifying the policy itself needs a Postgres-backed run.

**Two tests pin current behaviour rather than desired behaviour**, and should be
flipped when the underlying issues are fixed:

- `test_partial_update_is_rejected` — `PATCH /application/` requires all six
  fields, because `ApplicationUpdateSchema` declares them as `T | None` with no
  default (required-but-nullable in Pydantic v2).
- `test_history_of_another_users_application_is_readable` — `/application/history`
  performs no ownership check and returns other users' data.

**Frontend has no tests.** No runner is configured in `frontend/package.json`.
