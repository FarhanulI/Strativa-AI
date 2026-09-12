# Day 16 — Publishing Foundation (revised: cancel + concurrency-safe scheduler)

## 1. Day 16 Goal

Introduce `PublishedContent` as the record of a `ContentDraft` going live,
closing the "Publish" stage of the core product loop:

```text
Understand -> Decide -> Brief -> Create -> Publish -> Measure -> Learn
```

Manual publish confirmation is the MVP mechanism: a user marks an already
eligible draft as published, optionally pasting the external URL themselves,
or schedules it for a future time and can cancel that schedule before it
fires. A lightweight in-process poller promotes scheduled items once they are
due, guarded so it cannot double-process a row even if more than one app
instance runs it. Real platform publishing (OAuth, Facebook/Instagram/TikTok/
etc. API calls) stays behind the existing Day 9 adapter interface as a future
implementation.

## 2. Ownership

- **Owns**: `PublishedContent` lifecycle, including `scheduled` and
  `cancelled` states, and a lightweight in-process scheduler that promotes due
  items to `published`.
- **Consumes**: `ContentDraft` (existing, read-only from this feature's
  perspective — publishing never mutates a draft's own fields).
- **Does not own**:
  - A general job/task queue system. The scheduler is a narrow,
    single-purpose poller (one method, one table, no persisted job records,
    no worker pool) — not infrastructure for future async work. It does not
    use `app/workers/` (arq/Redis) and is not a precedent for adding one.
  - Retry-on-failure logic for the actual platform publish call. Real
    platform publish calls don't exist yet — publishing still goes through
    the manual/no-op `ManualPlatformAdapter` from Day 9's adapter contract, so
    there is nothing yet for a retry policy to protect against.

## 3. What Was Built

- `PublishedContent` model: `draft_id` (FK `content_drafts`, `CASCADE`),
  `profile_id` (FK `content_profiles`, `CASCADE`), `platform`, `external_url`
  (nullable), `scheduled_at` (nullable — set only for scheduled items),
  `published_at` (nullable — set only once actually published),
  `publish_method` (`manual` | `api` — only `manual` is implemented),
  `status` (`scheduled` | `published` | `failed` | `retracted` | `cancelled`),
  `created_at`. A composite index on `(status, scheduled_at)` makes the
  scheduler's due-row query cheap.
- Eligibility (shared by immediate publish and scheduling): a draft must be
  `ready` or `approved` (`ContentDraft.status`); any other status raises
  `DraftNotEligibleError` -> `409 Conflict`. Publishing/scheduling never
  mutates the draft's own fields (hook, body, caption, title, brief link, or
  the draft's own status).
- `PublishedContentService.publish_draft`: validates the workspace -> profile
  -> draft ownership chain and eligibility, then immediately creates a
  `PublishedContent` record with `status=published` and `published_at=now`.
- `PublishedContentService.schedule_draft`: same ownership/eligibility
  validation, but creates a `PublishedContent` record with `status=scheduled`
  and a required `scheduled_at` timestamp instead of publishing immediately.
  Rejects a `scheduled_at` that is not in the future with
  `422 Unprocessable Content` (`InvalidScheduleError`).
- `PublishedContentService.cancel_schedule`: moves a `scheduled` record to
  `cancelled` if it hasn't fired yet. Rejects any other status (already
  `published`, `failed`, `retracted`, or already `cancelled`) with
  `409 Conflict` (`ScheduleNotCancellableError`) — retracting an already
  `published` item is intentionally out of scope (no retract flow exists).
- `PublishedContentService.promote_due` / `PublishedContentRepository.claim_due`:
  the single operation the scheduler calls each tick. It performs one atomic
  `UPDATE published_content SET status='published', published_at=:now WHERE
  status='scheduled' AND scheduled_at <= :now RETURNING *`, then calls
  `ManualPlatformAdapter.publish(...)` for each claimed row. The `WHERE
  status='scheduled'` guard is the concurrency safeguard called for in this
  revision: if this ever ran from more than one app instance, only one
  instance's UPDATE can match and flip a given row, so the same row can never
  be claimed twice — cheap insurance, not premature scaling, since the MVP
  is still single-instance. No retry, no backoff, no dead-letter handling.
- `PublishScheduler` (`app/services/publish_scheduler.py`): an in-process
  `asyncio` task, not a queue worker. It repeatedly calls `promote_due` on its
  own DB session (`app.core.database.async_session_factory`) every
  `settings.publish_scheduler_poll_seconds` (default 30s), started/stopped via
  the FastAPI `lifespan` context in `app/main.py`. Controlled by
  `settings.publish_scheduler_enabled` (default `True`). A tick failure is
  logged and does not stop the loop.
- Extended the Day 9 `SocialPlatformAdapter` Protocol
  (`app/integrations/social.py`) with an async `publish(...)` method and added
  a `ManualPlatformAdapter` no-op implementation — the existing adapter
  contract is reused, not redesigned, and both the immediate-publish and
  scheduled-promotion paths call the same adapter method.
- API:
  - `POST /api/v1/profiles/{profile_id}/drafts/{draft_id}/publish`
  - `POST /api/v1/profiles/{profile_id}/drafts/{draft_id}/schedule`
    (body: `scheduled_at`, optional `external_url`)
  - `POST /api/v1/profiles/{profile_id}/published/{published_id}/cancel`
  - `GET /api/v1/profiles/{profile_id}/published` (filter by `platform` and
    `status`, paginated, ordered by `created_at` descending)
  - `GET /api/v1/profiles/{profile_id}/published/{published_id}` (full
    lineage: published record -> draft -> brief -> opportunity)
- Alembic migrations:
  - `m6n7o8p9q0` creates the `published_content` table with native Postgres
    enums for `publish_method` and `status`, FKs, and indexes on `draft_id`,
    `profile_id`, `platform`, `status`, `published_at`, `created_at`.
  - `n7o8p9q0r1` adds the `scheduled` and `cancelled` enum values, the indexed
    `scheduled_at` column, the composite `(status, scheduled_at)` index, and
    relaxes `published_at` to nullable. Its downgrade recreates the
    `publishstatus` enum without either added value (Postgres cannot drop
    individual enum values directly).
- Router -> Service -> Repository layering, matching every prior day.

## 4. Explicitly Out of Scope (confirmed not built)

- OAuth flows or any real Instagram/TikTok/Facebook/YouTube/LinkedIn/X API
  calls.
- A general job/task queue system (arq/Redis worker, persisted job records,
  retries, backoff) — the scheduler is a narrow poller against one table.
- Retry-on-failure logic for the platform publish call itself.
- Retracting or editing an already-`published` item (only a not-yet-fired
  `scheduled` item can be cancelled).
- Performance/metrics ingestion from published content — that is Day 17.

## 5. Security

Workspace/profile ownership is enforced identically to draft endpoints: every
lookup validates the full `Workspace -> ContentProfile -> ContentDraft ->
PublishedContent` chain, and any mismatch returns `404`. An ineligible-draft-
status or not-cancellable-schedule case returns `409` (resource is owned and
found but not in the required state), and an invalid `scheduled_at` value
returns `422` (client input problem, not an ownership or state conflict).

## 6. Definition of Done

- [x] `PublishedContent` model exists with `draft_id`, `profile_id`,
      `platform`, `external_url`, `scheduled_at`, `published_at`,
      `publish_method`, `status` (`scheduled` | `published` | `failed` |
      `retracted` | `cancelled`), `created_at`.
- [x] Service validates draft eligibility (`ready` or `approved`) before
      publishing or scheduling.
- [x] Service does not mutate the draft's strategic fields.
- [x] Cancel-schedule endpoint moves a `scheduled` item to `cancelled` and
      rejects cancelling a non-`scheduled` item with `409`.
- [x] `SocialPlatformAdapter.publish(...)` reused as a typed placeholder with a
      `ManualPlatformAdapter` no-op implementation shared by both the
      immediate-publish and scheduled-promotion paths — no real provider
      wired.
- [x] `promote_due`/`claim_due` uses a single atomic guarded `UPDATE` so a
      due row can never be claimed twice, even from a second app instance.
- [x] Composite index on `(status, scheduled_at)` backs the poller's query.
- [x] POST publish, POST schedule, POST cancel, GET list (filterable), GET
      single-with-lineage APIs exist.
- [x] `PublishScheduler` in-process poller wired into app `lifespan`, with no
      persisted job records and no general queue infrastructure.
- [x] Alembic migrations exist with FKs, indexes, and downgrade paths; single
      migration head.
- [x] Workspace/profile ownership enforced with 404 on any chain mismatch.
- [x] Tests cover: publish eligible draft (`ready` and `approved`), reject
      ineligible-status draft, schedule creation, reject past `scheduled_at`,
      reject scheduling an ineligible draft, cancel a scheduled item and its
      exclusion from promotion, reject cancelling a non-scheduled item, cancel
      ownership isolation, `promote_due` promoting only due items, the atomic
      claim rejecting a second promotion attempt on the same row,
      list/filter by platform and status, ownership isolation, lineage
      correctness.
- [x] Full regression suite passes (216 tests, including 14 in
      `tests/test_published_content.py`).
- [x] Ruff check and format check clean for touched files (repo-wide
      pre-existing violation count unchanged at 29).
- [x] Single migration head (`n7o8p9q0r1`).
