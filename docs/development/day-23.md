# Day 23 - Platform Connections: OAuth for YouTube, Facebook & Instagram

## Objective

Secure OAuth 2.0 connect/disconnect flows for YouTube, Facebook, and
Instagram — including destination selection so each `ContentProfile`'s
connection points at the correct specific Page/Channel, not merely the
authenticated account as a whole — with encrypted token storage,
proactive refresh, and real implementations of the Day 9 platform adapter
contract's connection/authorization surface. No publish-call wiring this
day (Day 24).

Full architectural context: `docs/product/product-architecture.md`
("Social Platform Architecture," "Platform Security Boundary," "AI
Execution and Job Control" — the scheduled-refresh pattern mirrors that
section's job-control principles) and `docs/development/progress.md`
(Day 9 platform adapter contracts, Day 20 authentication, Day 21
ownership-chain enforcement, Day 15 job infrastructure).

### Central design point

One OAuth login is not one publishable destination. A person has one
Facebook login but may administer several Facebook Pages; one Google
login but may manage several YouTube channels (Brand Accounts);
Instagram publishing goes through a Business Account linked to a
specific Facebook Page. Since a workspace can hold multiple
`ContentProfile`s (Model A, already established in this codebase), two
different profiles may need to publish to two **different**
Pages/Channels even though they're authorized through the **same**
underlying social login. The OAuth flow therefore has an explicit
"which Page/Channel is this for" destination-selection step between
token exchange and persisting a `PlatformConnection` — it never assumes
the first (or only) destination an API returns is the correct one.

## Scope

In scope:

- `PlatformConnection` model: `workspace_id`, `profile_id`, `platform`
  (`youtube` | `facebook` | `instagram`), `external_account_id` (the
  specific Page ID / Channel ID / Instagram Business Account ID this
  connection publishes to — never the top-level user/account ID),
  `external_account_name`, `access_token_encrypted` (envelope-encrypted
  at rest; the Page-scoped token for Facebook/Instagram, not the user
  token), `refresh_token_encrypted` (envelope-encrypted, nullable —
  per-platform lifecycle, not identical across platforms),
  `token_expires_at`, `scopes_granted`, `status` (`connected` |
  `disconnected` | `expired` | `revoked`), `connected_at`,
  `last_refreshed_at`.
- OAuth initiate endpoint: authorization URL with a signed CSRF `state`
  parameter (encoding the target `profile_id`) and an allowlisted
  redirect URI — never an open redirect.
- OAuth callback endpoint: exchanges the code for a USER-level token,
  validates state, fetches the available Pages/Channels for that
  authenticated account. Does **not** persist a `PlatformConnection`.
- Destination-selection endpoint: given the pending connection and a
  chosen `external_account_id` from the fetched list, derives the
  correct scoped token for that destination and persists the final
  `PlatformConnection` against the `profile_id` encoded in state.
  Rejects a selection not present in the originally fetched list.
- Destination fetching per platform:
  - Facebook/Instagram: `/me/accounts`, listing every Page the
    authenticated user administers, each with its own Page Access
    Token; for Instagram, the linked `instagram_business_account` per
    Page.
  - YouTube: `channels.list(mine=true)`, listing every channel
    (including Brand Account channels) the Google account manages.
- Pending-connection state in Redis (Day 15 connection): the user-level
  token and fetched destination list, encrypted, short TTL (default
  600s), keyed by a one-time selection token. An abandoned OAuth attempt
  simply expires, never leaves a dangling credential.
- Disconnect endpoint: revokes with the platform where supported, then
  deletes the stored credential (hard delete, not a soft-delete of a
  live credential).
- Application-level envelope encryption (KEK/DEK, AES-256-GCM) for every
  token, using a keyring supplied by the deployment's secrets manager —
  never a bare database column. `access_token`/`refresh_token` never
  stored or logged in plaintext, pending or final.
- Proactive token refresh: a Day 15 scheduled job (arq `cron_jobs`)
  refreshing near-expiry connections; on failure, `status=expired` and
  surfaced, never a silent failure at publish time.
- Real `PlatformAdapter` implementations for YouTube (Data API),
  Facebook (Graph API, Page-level publishing), and Instagram (Graph API
  via the linked Facebook Business account) — the Day 9 contract's
  connection/authorization surface only; publish methods typed/stubbed,
  not called.

Explicitly out of scope this day:

- TikTok, LinkedIn, X.
- Wiring connections into the actual publish flow (Day 24).
- Any UI for the OAuth consent screen or destination-selection step
  beyond the driving API endpoints.
- Reusing a prior OAuth grant to skip destination selection when
  connecting a second profile under the same social login — each
  connect attempt re-runs the full flow. A known, accepted UX
  trade-off, not a bug.

## Implementation

### `PlatformConnection` model (`app/platform_connections/models.py`)

- Unique constraint on **`(profile_id, platform)`, not
  `(workspace_id, platform)`** — under Model A, two profiles in one
  workspace can each hold their own independent connection, potentially
  to different Pages/Channels. Reconnect replaces the existing row
  rather than duplicating it.
- Index on `(status, token_expires_at)` for the refresh job's due-item
  query. Rows with a NULL `token_expires_at` (a non-expiring Page token)
  are excluded from that query on purpose.
- `__repr__` deliberately excludes every token column, so a repr in a
  traceback or log line can never carry a credential.

### Per-platform token lifecycle (genuinely not uniform)

- **YouTube/Google**: short-lived access token (~1h) plus a long-lived
  refresh token, requested via `access_type=offline&prompt=consent`.
  Google issues **no per-channel credential** — the account token
  authorizes uploads and the channel choice rides on
  `external_account_id` alone. Recorded explicitly as
  `connection_metadata.token_scope="account"` rather than left
  ambiguous.
- **Facebook/Instagram**: the code exchange yields a short-lived user
  token, immediately upgraded to a long-lived one (~60 days) via
  `grant_type=fb_exchange_token`, because a Page token derived from a
  long-lived user token does not expire. There is no refresh-token
  grant at all, so `refresh_token_encrypted`/`token_expires_at` are
  legitimately NULL. The **Page-scoped** token is stored; the
  user-level token is never persisted to Postgres.
- Whether a platform issues a destination-scoped credential is a
  **declared per-provider property** (`issues_destination_token`),
  never inferred from whether a token happened to appear in an API
  response — inferring would let a Page that returned no `access_token`
  silently fall back to storing the account-wide user token while
  labelling it destination-scoped.

### Destination fetching

- **Facebook** (`oauth/facebook.py`): `GET /me/accounts` returns every
  administered Page with its own Page Access Token in the same
  response. A Page with no `access_token` is filtered out rather than
  offered.
- **Instagram** (`oauth/instagram.py`, subclasses `FacebookOAuthProvider`
  — the OAuth grant genuinely is Facebook's): the same `/me/accounts`
  call requesting `instagram_business_account` per Page. A Page with no
  linked Business Account is excluded entirely; `external_account_id`
  is the Instagram Business Account ID, with the originating Page ID
  kept in `metadata`.
- **YouTube** (`oauth/youtube.py`): `channels.list(mine=true)`, every
  channel the account manages, Brand Accounts included.
- An account with zero publishable destinations gets a 422 with a clear
  message rather than an empty picker, and no credential is parked in
  Redis for it.

### Pending-connection state (`app/platform_connections/pending.py`)

Redis-backed (Day 15 connection), keyed by a one-time `selection_token`,
TTL `oauth_pending_connection_ttl_seconds` (default 600s). Every token in
the blob — the user token and each per-destination Page token — is
envelope-encrypted before it reaches Redis. `consume` uses `GETDEL`, so
the selection token is genuinely single-use; a replay finds nothing.

### Token encryption (`app/platform_connections/crypto.py`)

Envelope encryption: a fresh 256-bit DEK per call AES-256-GCMs the
token; the DEK is wrapped under a KEK from
`settings.token_encryption_keys` (a keyring, `key_id -> base64 key`).
Only wrapped DEKs are stored; the KEK never touches Postgres or Redis.
Ciphertext carries its own `key_id`
(`v1.<key_id>.<wrapped_dek>.<ciphertext>`), which is what makes the
scheme rotation-compatible without a column or migration change: add a
new key to the keyring, repoint `token_encryption_active_key_id`, and
old blobs keep resolving their own key id while new writes use the new
one. Rotation itself is out of scope this day; the compatibility is
documented and structurally supported.

### CSRF state (`app/platform_connections/state.py`)

HMAC-SHA256-signed, expiring, encoding the target `profile_id`. Signed
with a dedicated `oauth_state_secret` (falls back to the JWT secret only
in development). A valid signature proves the state was issued by this
system — nothing about who is presenting it now — so the state-encoded
`profile_id` is re-verified against the caller's actual
`require_profile_access`-verified profile at **both** the callback and
the destination-selection step, closing the replay path where a state
minted for profile A is presented against profile B.

### Endpoints (`app/platform_connections/router.py`)

All nested under `/profiles/{profile_id}/...`, so Day 21's
`require_profile_access` applies natively; `workspace_id` remains a
query parameter validated by `require_workspace_access`, matching the
convention every other profile-scoped router already uses. No route
trusts a bare client-supplied `workspace_id`/`profile_id`.

```text
POST   /api/v1/profiles/{profile_id}/platform-connections/{platform}/authorize
POST   /api/v1/profiles/{profile_id}/platform-connections/{platform}/callback
POST   /api/v1/profiles/{profile_id}/platform-connections/{platform}/select-destination
GET    /api/v1/profiles/{profile_id}/platform-connections
DELETE /api/v1/profiles/{profile_id}/platform-connections/{platform}
```

No endpoint accepts or returns a token; `PlatformConnectionResponse` has
no token field, so a credential cannot leak by accidental omission.

### Security

- Redirect URI allowlist is **exact-match**, never a prefix/`startswith`
  test (which would accept `https://app.example.com.evil.test/` and
  hand the authorization code to an attacker).
- Minimum viable scopes per platform — YouTube: `youtube.readonly` +
  `youtube.upload` (not the broad `youtube` scope); Facebook:
  `pages_show_list`, `pages_read_engagement`, `pages_manage_posts`;
  Instagram: those plus `instagram_basic`, `instagram_content_publish`.
  No ads, insights, messaging, or user-profile scopes.
- `Settings` rejects, outside development: the built-in development
  KEK, an unset `oauth_state_secret`, the default localhost redirect
  allowlist, and any non-`https` redirect entry — mirroring the
  existing `jwt_secret_key` validator.

### Disconnect

Revokes with the platform where supported (Google:
`oauth2.googleapis.com/revoke`), then hard-deletes the row regardless of
what the platform answers. Facebook/Instagram revocation is
best-effort: full app de-authorization needs the *user* token, which
this day deliberately never persists, so `DELETE /me/permissions` is
attempted with the Page token instead.

### Proactive refresh (`app/platform_connections/refresh.py`)

Registered as an arq **cron job** (`WorkerSettings.cron_jobs`, every 15
minutes — well inside the default 1-hour
`platform_connection_refresh_threshold_seconds`). Not an in-process API
poller like Day 17's `PublishScheduler`; not a queued
`execute_ai_job` task type, since nothing submits it — it is
time-driven, not request-driven. On failure the connection is marked
`status=expired` with the reason recorded in metadata, rather than left
looking `connected` to fail opaquely at publish time. Each connection
refreshes and commits independently, so one bad credential cannot stall
the rest of the batch.

### Platform adapters (`app/platform_connections/adapters.py`)

`YouTubeAdapter`, `FacebookAdapter`, `InstagramAdapter` behind a
`PlatformConnectionAdapter` Protocol that literally extends Day 9's
`SocialPlatformAdapter` (`app/integrations/social.py`). Implements the
connection/authorization surface Day 9 anticipated
(`authorization_url`, `exchange_code`, `list_destinations`,
`refresh_token`, `disconnect`, `access_token`). `publish` is a typed
stub that **raises** rather than faking success — a stub that returned a
plausible result would be worse than one that refuses, because Day 24
would then have nothing to notice. `get_adapter` is the uniform lookup
Day 24 will consume connections through.

### Review findings fixed during this day

An independent architecture/security review found one blocking issue
and several should-fixes before testing completed; all were fixed in
the same pass, each with a regression test:

- **Blocking**: the migration created the Postgres enum types with
  lowercase `.value` labels, but `SqlEnum(PyEnum)` binds the member
  *name* (`'YOUTUBE'`, not `'youtube'`) — every insert would have failed
  on real PostgreSQL, and the SQLite test suite structurally cannot
  catch this (SQLite renders `Enum` as `VARCHAR + CHECK` from the same
  model metadata, so both sides agree there). Fixed to uppercase member
  names, matching the repo's own precedent (`o8p9q0r1s2`'s `jobstatus`).
  A new test compares the migration's literals against the ORM's actual
  bind output, and was verified to fail against the old values.
- Destination-scoping was inferred from response data rather than
  declared, which could silently store the account-wide user token
  while labelling it destination-scoped. Fixed via
  `issues_destination_token` (see "Per-platform token lifecycle"
  above).
- Concurrent destination selection for the same `(profile, platform)`
  raised an unhandled `IntegrityError` (500); now normalized to a 409
  `ConnectionConflictError`, matching the Day 13 variation-selection
  precedent.
- A malformed 2xx platform response raised a bare `KeyError` (500)
  instead of the module's deliberate 502; fixed via a shared
  `require_access_token` helper.
- Redirect-URI allowlist and encryption-key validation hardened
  outside development; an account with no publishable destination now
  returns 422 instead of parking a live credential in Redis.

A pre-existing instance of the same enum-label bug class was found (not
introduced by this day) in Day 22's
`x7y8z9a0b1_add_onboarding_status_and_profile_fields.py` and logged as a
known limitation rather than fixed, since it belongs to an already-landed
migration from another day.

## Migration

- `y8z9a0b1c2` (head, down-revision `x7y8z9a0b1`) creates
  `platform_connections` with the `(profile_id, platform)` unique
  constraint, the `(status, token_expires_at)` composite index, and
  `workspace_id`/`profile_id` indexes, plus the `socialplatform`/
  `connectionstatus` enum types (uppercase member-name labels — see
  "Review findings fixed" above). Reversible; single head confirmed via
  `uv run alembic heads`.

## Testing

46 tests in `tests/test_platform_connections.py`. Every platform fixture
returns **more than one** destination (3 Facebook Pages, 3 YouTube
channels including Brand Accounts, 2 Instagram Business Accounts),
because a single-destination fixture cannot detect "persisted the first
destination returned" — the precise bug this day exists to prevent. All
outbound platform HTTP goes through an `httpx.MockTransport`; no test
reaches the network.

Coverage includes: state signing/tampering/expiry/cross-profile
rejection; redirect-URI allowlist rejection including the
exact-vs-prefix case; multi-destination callback for all three
platforms; Instagram correctly excluding a Page with no linked Business
Account; callback persisting nothing; unknown-destination selection
rejected; destination-scoped token stored (not the user token), asserted
against both; YouTube's account-scoped token recorded deliberately; two
profiles in one workspace selecting two different Pages and ending up
with two independent rows; reconnect replacing rather than duplicating;
single-use selection token; ciphertext-at-rest in both Postgres and
Redis; pending state expiring from Redis if never finalized; disconnect
revoking and removing (with and without successful revocation); refresh
success/failure/no-refresh-token paths; the due-query and the scheduled
job's batch; unauthenticated 401; cross-workspace 404 across both halves
of the ownership chain; the migration enum-label regression guard; and
the review-finding regressions (Page-without-token, concurrent
selection, malformed platform response, no-destination rejection).

Verification (all actually executed):

- `uv run pytest tests/test_platform_connections.py -q` → 46 passed.
- `uv run pytest -q` → 28 failed, 328 passed. The 28 are byte-identical
  by name to the pre-existing Day 21 baseline (`test_workspaces.py`,
  `test_intelligence_analysis.py`, `test_published_content.py`,
  `test_content_intelligence_synthesis.py`) — no new regressions.
- `ruff check`/`ruff format --check` clean for every Day 23 file;
  repo-wide pre-existing violation counts unchanged and none in files
  this day touched.
- `uv run alembic heads` → `y8z9a0b1c2` (single head).

## Known limitations

- **End-to-end verification against a real sandbox account with more
  than one Page/Channel has not been performed.** No Meta or Google
  OAuth client credentials are configured in this development
  environment; every platform interaction is exercised against a mock
  transport shaped to the real API responses. This is the one
  Definition-of-Done item not yet satisfied, and it is specifically the
  item meant to catch a wrong-destination bug that a single-destination
  test account would hide.
- The migration has not been run against a real PostgreSQL instance
  (project convention). The new enum-label test compensates for the
  specific failure mode that convention would otherwise hide, but is
  not a substitute for a real migration run.
- Envelope ciphertext uses no AES-GCM associated data, so a ciphertext
  is technically portable between rows for someone with database write
  access. Low severity; cheap to harden later.
- **Meta app review should start now, in parallel with future days.**
  `pages_manage_posts`, `instagram_content_publish`,
  `pages_read_engagement`, and `pages_show_list` all require Meta App
  Review before they work outside the app's own dev/test users, and
  that review takes calendar time independent of engineering effort.
  YouTube needs its own Google OAuth verification for `youtube.upload`
  on similar footing.
- Reusing a prior OAuth grant to skip destination selection for a
  second profile under the same social login is not implemented — an
  accepted UX trade-off, not a bug.

## Files changed

- New: `app/platform_connections/__init__.py`, `models.py`, `crypto.py`,
  `state.py`, `pending.py`, `repository.py`, `service.py`, `schemas.py`,
  `router.py`, `adapters.py`, `refresh.py`, `oauth/__init__.py`,
  `oauth/base.py`, `oauth/youtube.py`, `oauth/facebook.py`,
  `oauth/instagram.py`,
  `migrations/versions/y8z9a0b1c2_add_platform_connections.py`,
  `tests/test_platform_connections.py`.
- Modified: `app/core/config.py` (Day 23 settings block + production
  validator), `app/workers/settings.py` (arq `cron_jobs` entry),
  `app/models/__init__.py`, `app/api/v1/router.py`, `app/integrations/
  social.py` (docstring cross-reference to the new adapter surface),
  `pyproject.toml` (`httpx` promoted from dev-only to a runtime
  dependency; `cryptography` added).
