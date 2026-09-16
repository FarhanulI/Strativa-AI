# Day 20 — Authentication Foundation: JWT Issuance, Refresh & Redis-Based Revocation

Read and follow:
- `CLAUDE.md`
- `docs/product/product-architecture.md`
- `docs/development/progress.md` (Days 15, 19)

## Objective

Introduce real authentication (login, refresh, logout, password reset) backed
by JWT access tokens and Redis-based revocation, and point the Day 15 rate
limiter at real authenticated identity instead of a client-supplied header.

## Scope correction

Code inspection at the start of this day confirmed there is no
ownership-chain enforcement anywhere in the codebase: `WorkspaceMember.user_id`
is a bare `String(255)`, not a foreign key; every Day 15-19 router trusts a
client-supplied `workspace_id`/`profile_id` with no verification; the Day 15
rate limiter's identity was an `X-User-Id` header or client IP. This is a
live IDOR vulnerability, independent of JWT auth.

**Decision**: Day 20 = Section 1 (Authentication) ONLY. No ownership-chain
retrofit on Days 15-19 routers. The one exception: patch the Day 15 rate
limiter's identity source to use real JWT identity instead of
`X-User-Id`/IP.

## Scope note

MVP: one User maps to exactly one Workspace. This day authenticates an
EXISTING user against an EXISTING workspace only — login, refresh, logout,
password reset. No registration/signup endpoint. User/Workspace are seeded
directly via fixtures, matching the Days 15-19 test-seeding convention.

## In scope

- `User` credential model; argon2 password hashing with a documented cost
  factor.
- `POST /auth/login` — short-TTL access token + longer-TTL refresh token.
- `POST /auth/refresh` — rotates the refresh token; reuse of an
  already-rotated token is rejected and revokes the whole session.
- `POST /auth/logout` — adds the access token's `jti` to a Redis revocation
  list with TTL = its remaining validity, and revokes the refresh token's
  session; reuses the Day 15 Redis connection (no second client).
- `get_current_user` JWT verification dependency — validates signature and
  expiry, checks `jti` against Redis, populates authenticated-user context;
  reusable by future protected routes (Day 21+).
- JWT claims: `sub`, `jti`, `iat`/`exp`, and `workspace_ids` as a fast-path
  hint only — never sufficient by itself for authorization.
- Password reset: request + confirm, token-based, time-limited, single-use,
  with a stubbed/logged email delivery path.
- `POST /auth/login` registered under the Day 15 rate-limit middleware with
  its own tight policy (`RouteCategory.AUTH_LOGIN`).
- Patch the Day 15 rate limiter to read identity from `get_current_user`'s
  JWT instead of `X-User-Id`/IP.

## Out of scope

- Signup/registration.
- Ownership-chain enforcement on Days 15-19 routers (tracked as Day 21 —
  see "Known critical gap" below).
- Foreign key from `WorkspaceMember.user_id` to `User.id`.
- OAuth, MFA.
- New rate-limiting/job-queue/caching infrastructure.

## System design

- Redis key `revoked_jti:{jti}`, TTL = remaining access-token lifetime,
  self-expiring, on the shared Day 15 Redis connection
  (`app.infrastructure.redis_client.get_redis()`).
- Refresh tokens and password reset tokens are opaque, high-entropy values
  (`secrets.token_urlsafe(48)`), stored server-side only as a SHA-256 hash —
  the raw value is never persisted.
- Refresh rotation: each successful refresh revokes the presented token and
  issues a new one in the same `session_id`; presenting an already-revoked
  token revokes the entire session (defense-in-depth against token replay
  after theft).
- HS256 signing for this single-backend MVP (asymmetric signing only earns
  its complexity once a second service needs to verify tokens
  independently).
- `User.id` is a UUID, matching `ContentProfile`/`Workspace` convention and
  compatible with a future FK from `WorkspaceMember.user_id`.
- JWT signing key is environment-driven; a hardcoded/default secret is
  rejected outside local dev (`_INSECURE_DEFAULT_JWT_SECRET_KEY` +
  validator in `app/core/config.py`).

## Architecture

New `app/auth/` module: `models.py` (`User`, `RefreshToken`,
`PasswordResetToken`), `security.py` (password hashing, opaque token
generation/hashing), `jwt.py` (encode/decode access tokens, bearer-token
extraction), `service.py` (`AuthService` — login/refresh/logout/password
reset), `dependencies.py` (`get_current_user`), `repository.py`. Registered
via `app/api/v1/auth.py` and `app/api/v1/router.py`. Does not touch Days
15-19 routers except the Day 15 rate-limit middleware's identity
extraction.

## Security

- Argon2 password hashing (documented cost factor in `app/auth/security.py`).
- Constant-time credential comparison (argon2's built-in verify).
- Identical error message for wrong-password and unknown-email
  (`"Invalid email or password"`), with a dummy-hash verify on the
  unknown-email path to avoid a timing side-channel.
- Refresh rotation with reuse detection.
- Immediate revocation correctness: logout is effective on the very next
  request, verified end-to-end via Redis.
- Login is rate-limited under a tight, dedicated policy.
- No sensitive data (passwords, raw tokens) in logs; the password-reset
  email stub logs the raw token only because no real email provider is
  configured yet — flagged in-code as unsafe for anything beyond local dev.

## Known critical gap (tracked for Day 21)

**Days 15-19 accept a client-supplied `workspace_id`/`profile_id` on every
request with no verification that the authenticated caller actually owns
or belongs to that workspace/profile.** `WorkspaceMember.user_id` remains a
bare, unenforced `String(255)`. This day adds real authentication but does
**not** retrofit ownership-chain enforcement onto any existing router — that
retrofit is out of scope here and is tracked as **Day 21 — Ownership-Chain
Enforcement Retrofit**. Days 15-19 must not be considered auth-complete
until Day 21 lands.

## Testing

Login success/failure; token validation/expiry rejection; refresh rotation;
reused stale refresh token rejected; logout revokes and an immediate
subsequent request is rejected; a revoked entry expires naturally at TTL;
password reset end-to-end (including reuse-after-confirm rejected); login
rate-limit test; rate limiter keys off real authenticated identity, not
`X-User-Id`/IP. All fixtures seed User/Workspace directly. No
ownership-chain regression tests were added (out of scope).

## Definition of Done

Tests pass; JWT signing key is environment-driven, never hardcoded; Redis
revocation verified end-to-end on the shared Day 15 connection; rate
limiter uses real authenticated identity; `progress.md` contains the
critical-gap note above; Ruff clean; migration reversible.

## Implementation note

Executed as scoped above.

**New files**: `app/auth/__init__.py`, `app/auth/models.py`,
`app/auth/security.py`, `app/auth/jwt.py`, `app/auth/service.py`,
`app/auth/dependencies.py`, `app/auth/repository.py`, `app/api/v1/auth.py`,
`migrations/versions/v5w6x7y8z9_add_auth_foundation.py`, `tests/test_auth.py`.

**Modified files**: `app/api/v1/router.py` (registers the auth router),
`app/infrastructure/ratelimit/policy.py` (`RouteCategory.AUTH_LOGIN` +
dedicated rule), `app/infrastructure/ratelimit/middleware.py` (identity
now comes from the verified JWT via `try_get_request_identity`, not
`X-User-Id`/IP), `app/core/config.py` (JWT/auth settings +
insecure-default-secret validator), `app/models/__init__.py` (registers
the new auth models for Alembic autogeneration), `tests/conftest.py`
(`client`, `_default_auth_redis_override`, `seed_workspace`, `seed_user`
fixtures).

**Database**: one migration (`v5w6x7y8z9`, head, down-revision
`u4v5w6x7y8`) adding `users`, `refresh_tokens`, `password_reset_tokens`.
Reversible `downgrade()` verified by reading (drops indexes then tables in
reverse order). Structural validation only — no Postgres instance is
available in this dev environment, so `alembic upgrade head` has not been
executed against a real database; the revision chain was confirmed to
resolve to a single head with no branching.

**Tests**: 12 new tests in `tests/test_auth.py`, all passing, exercising
every item in the Testing section above. Full-repo regression suite and
Ruff/format checks were run for this day's file set with no issues.

**Known issues / carried-forward gap**: the Days 15-19 IDOR gap described
above is unresolved by design and tracked as Day 21.
