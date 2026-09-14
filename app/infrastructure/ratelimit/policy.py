from dataclasses import dataclass
from enum import StrEnum

from app.core.config import settings


class RouteCategory(StrEnum):
    """Route categories the rate limiter applies a different ceiling to.

    AI_TRIGGERING covers routes that end up invoking (or will, once wired)
    the AI Router — briefs, drafts, variations, evaluations — which get a
    materially lower default limit than plain CRUD reads/writes. Individual
    routes are not yet hand-tuned; classification is by path prefix only.
    """

    CRUD = "crud"
    AI_TRIGGERING = "ai_triggering"


@dataclass(frozen=True)
class RateLimitRule:
    max_requests: int
    window_seconds: int


def classify_route(path: str) -> RouteCategory:
    for prefix in settings.ai_triggering_route_prefixes:
        if prefix in path:
            return RouteCategory.AI_TRIGGERING
    return RouteCategory.CRUD


def rule_for_category(category: RouteCategory) -> RateLimitRule:
    if category is RouteCategory.AI_TRIGGERING:
        return RateLimitRule(
            max_requests=settings.rate_limit_ai_requests_per_window,
            window_seconds=settings.rate_limit_window_seconds,
        )
    return RateLimitRule(
        max_requests=settings.rate_limit_crud_requests_per_window,
        window_seconds=settings.rate_limit_window_seconds,
    )


def reasoning_rule() -> RateLimitRule:
    """Per-profile ceiling on `opportunity_reasoning` job execution (Day 18)
    — applied inside the worker, not the HTTP middleware, so it throttles AI
    cost from a burst of newly-created opportunities rather than requests.
    """
    return RateLimitRule(
        max_requests=settings.rate_limit_reasoning_requests_per_window,
        window_seconds=settings.rate_limit_window_seconds,
    )
