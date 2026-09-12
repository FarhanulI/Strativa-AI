# Day 15 — Scalable Platform Foundation: Async Jobs, Caching & Connection Pooling

## 1. Day 15 Goal

This is a pure infrastructure day. No product/domain feature is built.
Everything here becomes a dependency for Days 16+ (background AI execution,
enrichment, and any future scheduling work).

Introduce, as reusable `app/infrastructure/` services:

- background job processing (arq + a durable `ai_jobs` status table)
- a shared cache (`CacheService`, not yet wired into any endpoint)
- Redis-backed rate limiting middleware
- Idempotency-Key handling for job-submission endpoints
- a distributed lock helper
- environment-driven database connection pool sizing and a statement timeout

This maps directly to docs/product/product-architecture.md's "AI Execution
and Job Control" (per-task timeouts, bounded retry with backoff, durable job
status, idempotency), "Data and Transaction Architecture" (connection
pooling, statement timeouts configured per environment), and the Stage 2
("Paid Beta") requirement that AI-heavy operations move to background jobs
with status and retry visibility.

## 2. In Scope

- `app/infrastructure/jobs/` — job submission (`submit_job`), a
  task-type → handler registry, the arq worker entrypoint
  (`execute_ai_job`), and Idempotency-Key dedup.
- `app/models/ai_job.py` / `app/repositories/ai_job.py` — the `AIJob`
  model and its repository, backing a Postgres `ai_jobs` table:
  `id, task_type, profile_id, status (queued|running|succeeded|failed|
  timed_out), attempts, submitted_at, started_at, finished_at, error,
  result_ref`, indexed on `(profile_id, status)` and `(status,
  submitted_at)`.
- `app/infrastructure/cache/` — `CacheService.get_or_compute/invalidate/
  invalidate_prefix`, namespaced keys, SCAN-based prefix invalidation
  (never `KEYS`). Not wired into any real endpoint yet.
- `app/infrastructure/ratelimit/` — a sliding-window Redis rate limiter
  applied per user-identifier and per workspace, with a lower default
  ceiling for a configurable set of "AI-triggering" route prefixes than
  for plain CRUD routes.
- `app/infrastructure/locks/` — `DistributedLock` (Redis `SET NX PX` via
  redis-py's built-in `Lock`, with a safe token-checked release), for a
  future scheduler (e.g. the Day 17 publish scheduler, if it ever needs to
  coordinate across more than one instance) to use.
- `app/workers/settings.py` — arq `WorkerSettings` now registers
  `execute_ai_job`; run with `uv run arq app.workers.settings.WorkerSettings`
  as a process separate from the API.
- `app/core/database.py` / `app/core/config.py` — explicit, environment-driven
  `pool_size`/`max_overflow`/`pool_timeout` and a connection-level
  `statement_timeout` (Postgres only; SQLite, used by the test suite, does
  not support either in the same sense and is left on library defaults).

## 3. Out of Scope

- Any product feature (Intelligence, Opportunity, Library, Publishing).
- Wiring `CacheService` into a real read path.
- Wiring the rate limiter's route classification per actual endpoint
  beyond the default "AI-triggering" prefix list — no per-route tuning.
- Multi-region infrastructure, read replicas, Kubernetes/autoscaling.
- A real authenticated-user identity (none exists yet in this codebase —
  see docs/product/product-architecture.md "Identity, Tenancy, and
  Authorization"). The rate limiter's "per user" bucket is a best-effort
  placeholder keyed on an `X-User-Id` header or client address until real
  auth lands; it is not an authorization boundary.

## 4. Architecture

```text
Domain Service
      |
      v  (never imports Redis/queue clients directly)
app/infrastructure/{jobs,cache,ratelimit,locks}
      |
      v
Redis (broker + cache + rate-limit counters + locks) / Postgres (ai_jobs)
```

`app/infrastructure/jobs/service.submit_job` creates the durable `AIJob`
row and enqueues the arq job in the same call, using the row's own id as
arq's `_job_id` so submission-level idempotency and status tracking share
one identifier. The worker (`execute_ai_job`) opens its own DB session
(it runs in a separate process), transitions `queued -> running`, dispatches
to a registered handler by `task_type` with a per-job `asyncio.wait_for`
timeout, and on failure or timeout re-enqueues with exponential backoff
(`base * 2^(attempt-1)`) until `job_max_attempts` is exhausted, at which
point the row becomes a terminal `failed` or `timed_out`. No product
`task_type` is registered yet — only an `infrastructure.echo` placeholder
handler exists, exercised by tests.

## 5. Rate Limiting Default

`rate_limit_enabled` defaults to **False**. This is foundational,
un-tuned-per-route middleware; flipping it on globally by default would
have made every existing test that exercises the live `app` instance over
HTTP depend on a reachable Redis. Staging/production environments enable it
via env var once Redis is actually deployed there. The middleware itself,
its policy, and its Redis-backed sliding window are fully implemented and
covered by tests using a fake Redis client — only the default is off.

## 6. Testing

- Job submission → worker execution → status transition, both success and
  forced-failure/retry-exhaustion and timeout paths
  (`tests/test_infrastructure_jobs.py`).
- Cache get/set (`get_or_compute`), `invalidate`, `invalidate_prefix`
  (`tests/test_infrastructure_cache.py`).
- Simulated connection-pool exhaustion confirms a bounded, catchable
  `TimeoutError` rather than a hang or crash
  (`tests/test_infrastructure_pool.py`).
- Rate limiter blocks after the configured threshold and resets after the
  window, at both the raw sliding-window level and through the live
  middleware (`tests/test_infrastructure_ratelimit.py`).
- Idempotency key prevents a duplicate claim within the TTL window
  (`tests/test_infrastructure_idempotency.py`).
- Distributed lock: acquire/release, contended second holder fails fast
  (or after `blocking_timeout_seconds`), `try_lock` non-blocking variant
  (`tests/test_infrastructure_locks.py`).

No real Redis or Postgres instance is available in this development
environment (no running `redis-server`, no Docker daemon). Tests use
`fakeredis` for every Redis-backed piece and the project's existing SQLite
test-database convention for `AIJob` persistence — the same "fast
development-convenience substitute, real-instance validation happens in a
dedicated integration pipeline before release" pattern the project already
applies to Postgres (see docs/product/product-architecture.md, "Data and
Transaction Architecture"). The arq worker function (`execute_ai_job`) is
exercised directly as a coroutine rather than through a live
`arq.worker.Worker` loop, for the same reason.

## 7. Definition of Done

- Tests pass (with the fakeredis/SQLite substitution above documented as a
  known limitation, not a silent gap).
- `execute_ai_job` processes a job end to end (queued → running →
  succeeded, and separately the retry/backoff and timeout paths) against
  the test database and a stubbed arq pool.
- Pool sizing formula and values, and rate-limit defaults, documented in
  `docs/development/progress.md` under "Platform Infrastructure".
- Ruff clean.
