from functools import lru_cache

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


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
    publish_scheduler_enabled: bool = True
    publish_scheduler_poll_seconds: float = 30.0

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

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
