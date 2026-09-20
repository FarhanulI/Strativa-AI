from functools import lru_cache

from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

# Placeholder only -- never a real production signing key. `Settings`
# validates below that this exact value cannot be used outside
# `environment == "development"`.
_INSECURE_DEFAULT_JWT_SECRET_KEY = "insecure-dev-secret-change-in-production"

# Development-only placeholder KEK (32 zero-ish bytes, urlsafe-base64). Like
# the JWT secret above, `Settings` rejects it outside
# `environment == "development"` -- a real deployment supplies the keyring
# from its secrets manager. See app/platform_connections/crypto.py.
_INSECURE_DEFAULT_TOKEN_ENCRYPTION_KEY = "aW5zZWN1cmUtZGV2ZWxvcG1lbnQta2VrLTMyYnl0ZXM"

# Development-only OAuth redirect target; `Settings` rejects this exact
# default outside development, like the two secrets above.
_DEFAULT_OAUTH_REDIRECT_URI_ALLOWLIST = ["http://localhost:3000/oauth/callback"]


class Settings(BaseSettings):
    app_name: str = "AI Content Studio API"
    app_version: str = "0.1.0"
    environment: str = "development"
    log_level: str = "INFO"
    api_v1_prefix: str = "/api/v1"

    database_url: str = "postgresql+asyncpg://contentstudio:password@localhost:5432/contentstudio"
    redis_url: str = "redis://localhost:6379"
    backend_cors_origins: list[str] = Field(default_factory=lambda: ["http://localhost:3000"])
    llm_provider: str = "gemini"
    llm_model: str = "gemini-configured"
    gemini_api_key: str | None = None

    # Publishing (app/services/published_content.py, app/services/
    # publish_promotion.py) -- Day 24. Promotion runs as a Day 15 arq cron
    # job, not an in-process poller; see publish_promotion.py's module
    # docstring for why.
    #
    # Must evenly divide 60 -- expanded into that many second-of-minute
    # marks in app.workers.settings (arq cron fires on fixed marks, not an
    # arbitrary interval). Lower = scheduled publishes fire closer to their
    # scheduled_at, at the cost of an extra claim-query poll per worker per
    # tick.
    publish_promotion_interval_seconds: int = 30
    # A row is only ever stuck in `publishing` if a worker crashed mid-call;
    # comfortably longer than any real platform call should take.
    publish_stuck_publishing_timeout_seconds: int = 900
    publish_stuck_recovery_interval_minutes: int = 15

    # Database connection pool (see docs/development/progress.md "Platform
    # Infrastructure" for the sizing formula). Environment-driven so each
    # deployment tier can size the pool against its own Postgres
    # max_connections without a code change.
    db_pool_size: int = 10
    db_max_overflow: int = 5
    db_pool_timeout_seconds: float = 30.0
    db_statement_timeout_ms: int = 30_000

    # Background jobs (arq)
    job_timeout_seconds: float = 30.0
    job_max_attempts: int = 3
    job_retry_backoff_base_seconds: float = 2.0

    # Cache (app/infrastructure/cache)
    cache_default_ttl_seconds: int = 300
    # Strategic synthesis (app/content_intelligence) is the most expensive
    # reasoning call in the system -- a longer TTL than component analyses.
    cache_synthesis_ttl_seconds: int = 1800

    # Content Library (app/services/content_library.py) -- only the default
    # unfiltered, first-page, default-sort view is cached (highest-traffic
    # query pattern); a short TTL bounds staleness since drafts change often.
    library_default_view_cache_ttl_seconds: int = 30
    content_library_default_page_size: int = 20
    # Hard server-side cap regardless of client-requested page size --
    # cursor pagination is disallowed from ever returning unbounded pages.
    content_library_max_page_size: int = 50

    # Rate limiting (app/infrastructure/ratelimit) — a lower ceiling for
    # AI-triggering routes than plain CRUD routes; see policy.py.
    # Off by default: this is foundational middleware, not yet tuned per
    # route (see docs/development/day-15.md). Staging/production set this
    # true via env var once real Redis is available; the in-memory SQLite
    # test suite exercises it directly with a fake Redis instance instead of
    # flipping it on globally for every existing test.
    rate_limit_enabled: bool = False
    rate_limit_window_seconds: int = 60
    rate_limit_crud_requests_per_window: int = 120
    rate_limit_ai_requests_per_window: int = 20
    ai_triggering_route_prefixes: list[str] = Field(
        default_factory=lambda: [
            "/briefs",
            "/drafts",
            "/variations",
            "/evaluations",
        ]
    )

    # Per-profile rate limiting for opportunity_reasoning job execution (Day
    # 18) — reuses the Day 15 sliding-window limiter, but applied inside the
    # worker rather than the HTTP middleware: a burst of new opportunities
    # for one profile queues excess reasoning jobs rather than dropping or
    # failing them (see app.infrastructure.jobs.worker_tasks).
    rate_limit_reasoning_requests_per_window: int = 10

    # Idempotency-Key handling for job-submission endpoints
    idempotency_key_ttl_seconds: int = 600

    # Distributed locks (app/infrastructure/locks)
    lock_default_timeout_seconds: float = 30.0

    # Authentication (app/auth) -- Day 20. HS256 is used rather than RS256:
    # this is a single-backend MVP (one API process family sharing one
    # secret), so asymmetric signing buys nothing yet and adds key
    # management overhead; revisit if a separate service ever needs to
    # verify tokens without holding the signing secret.
    jwt_secret_key: str = _INSECURE_DEFAULT_JWT_SECRET_KEY
    jwt_algorithm: str = "HS256"
    jwt_access_token_ttl_minutes: int = 15
    jwt_refresh_token_ttl_days: int = 30
    password_reset_token_ttl_minutes: int = 30

    # Login-endpoint rate limiting (app/infrastructure/ratelimit) -- a much
    # tighter ceiling than plain CRUD/AI routes, applied by exact-path
    # match against `/auth/login`, specifically to resist credential
    # stuffing.
    auth_login_rate_limit_requests_per_window: int = 5
    auth_login_rate_limit_window_seconds: int = 60

    # Register-endpoint rate limiting -- same tight-ceiling rationale as
    # login, applied by exact-path match against `/auth/register`, to
    # resist automated mass-account creation.
    auth_register_rate_limit_requests_per_window: int = 5
    auth_register_rate_limit_window_seconds: int = 60

    # --- Platform connections (app/platform_connections) -- Day 23 ---

    # Envelope encryption keyring for stored OAuth credentials: a mapping of
    # `key_id -> urlsafe-base64 32-byte key`, supplied by the deployment's
    # secrets manager. A keyring rather than a single key specifically so a
    # future rotation can add a new key, repoint
    # `token_encryption_active_key_id`, and keep decrypting existing blobs
    # (each blob names its own key id) -- see app/platform_connections/crypto.py.
    token_encryption_keys: dict[str, str] = Field(
        default_factory=lambda: {"v1": _INSECURE_DEFAULT_TOKEN_ENCRYPTION_KEY}
    )
    token_encryption_active_key_id: str = "v1"

    # Signing secret for the OAuth CSRF `state` parameter. Separate from
    # `jwt_secret_key` so a state-signing compromise never implies an
    # access-token-forging compromise; falls back to the JWT secret only in
    # development, and is validated below outside it.
    oauth_state_secret: str | None = None
    oauth_state_ttl_seconds: int = 600

    # Redirect URIs an OAuth `authorize` call may ask the provider to send
    # the user back to. Exact-match allowlist -- never a prefix/substring
    # match, which is how open redirects get introduced.
    oauth_redirect_uri_allowlist: list[str] = Field(
        default_factory=lambda: list(_DEFAULT_OAUTH_REDIRECT_URI_ALLOWLIST)
    )

    # Pending (post-token-exchange, pre-destination-selection) connection
    # state lives in Redis only this long. An abandoned OAuth attempt simply
    # expires rather than leaving a dangling credential anywhere.
    oauth_pending_connection_ttl_seconds: int = 600

    # Per-platform OAuth client credentials.
    youtube_oauth_client_id: str | None = None
    youtube_oauth_client_secret: str | None = None
    facebook_oauth_client_id: str | None = None
    facebook_oauth_client_secret: str | None = None
    facebook_graph_api_version: str = "v21.0"

    # Proactive refresh (app/platform_connections/refresh.py, run as an arq
    # cron job). A connection is "due" once its access token expires within
    # this window; the cron cadence must stay well under it so a token is
    # seen as due several times before it actually lapses.
    platform_connection_refresh_threshold_seconds: int = 3600
    platform_connection_refresh_batch_size: int = 100

    # Outbound HTTP to platform OAuth/Graph endpoints.
    platform_http_timeout_seconds: float = 10.0

    # --- Learning Engine (app/learning) -- Day 26 ---
    #
    # Deterministic pattern extraction runs as a nightly arq cron job
    # (app.learning.extraction.extract_learnings_cron), not per-metrics
    # -submission, to bound AI/compute cost as the number of profiles and
    # PerformanceAnalysis records grows.
    learning_extraction_hour: int = 3
    learning_extraction_minute: int = 0
    # A profile needs at least this many analyzed ContentPerformance
    # records before extraction runs at all -- below this, dimension-value
    # comparisons are too noisy to call a "pattern".
    learning_extraction_min_analyses: int = 6
    # A dimension value (e.g. one format) needs at least this many analyzed
    # records of its own to be compared against the profile's overall
    # average -- avoids surfacing a "pattern" from a single lucky post.
    learning_extraction_min_group_size: int = 3
    # Minimum relative-engagement delta (vs. the profile's overall average)
    # for a dimension value to be surfaced as a candidate learning.
    learning_extraction_min_delta_threshold: float = 0.20

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    @property
    def resolved_oauth_state_secret(self) -> str:
        """The secret the OAuth `state` HMAC is keyed with.

        Falls back to `jwt_secret_key` only in development, where that value
        is itself the known-insecure placeholder; the validator below
        requires a real, distinct secret everywhere else.
        """
        return self.oauth_state_secret or self.jwt_secret_key

    @model_validator(mode="after")
    def _validate_platform_connection_secrets(self) -> "Settings":
        if self.environment == "development":
            return self

        if _INSECURE_DEFAULT_TOKEN_ENCRYPTION_KEY in self.token_encryption_keys.values():
            raise ValueError(
                "token_encryption_keys must be supplied from a secrets manager outside "
                "development (the built-in development key cannot encrypt real credentials)"
            )
        if self.token_encryption_active_key_id not in self.token_encryption_keys:
            raise ValueError(
                "token_encryption_active_key_id must name a key present in token_encryption_keys"
            )
        if not self.oauth_state_secret:
            raise ValueError(
                "oauth_state_secret must be set via environment/.env outside development"
            )
        # Fails closed rather than open if unset (connections just break),
        # but shipping the localhost default to production is an avoidable
        # surprise, and an http:// redirect would expose the authorization
        # code in transit.
        if self.oauth_redirect_uri_allowlist == _DEFAULT_OAUTH_REDIRECT_URI_ALLOWLIST:
            raise ValueError(
                "oauth_redirect_uri_allowlist must be set via environment/.env outside "
                "development (the localhost default is not a real redirect target)"
            )
        if any(not uri.startswith("https://") for uri in self.oauth_redirect_uri_allowlist):
            raise ValueError(
                "every oauth_redirect_uri_allowlist entry must use https outside development"
            )
        return self

    @model_validator(mode="after")
    def _validate_jwt_secret(self) -> "Settings":
        if (
            self.environment != "development"
            and self.jwt_secret_key == _INSECURE_DEFAULT_JWT_SECRET_KEY
        ):
            raise ValueError(
                "jwt_secret_key must be set via environment/.env outside development "
                "(never hardcode a production signing key)"
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
