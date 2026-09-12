from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.core.config import settings
from app.infrastructure.ratelimit.limiter import check_sliding_window
from app.infrastructure.ratelimit.policy import classify_route, rule_for_category
from app.infrastructure.redis_client import get_redis

_USER_HEADER = "X-User-Id"
_WORKSPACE_QUERY_PARAM = "workspace_id"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter, applied per user and per
    workspace, with a lower ceiling for AI-triggering routes than plain CRUD
    routes (see `policy.py`).

    Identity is not yet a platform concept (no auth layer exists per
    docs/product/product-architecture.md "Identity, Tenancy, and
    Authorization" — Stage 1 requirement, not yet built). Until it lands,
    the per-user bucket keys off an `X-User-Id` header when present and
    falls back to the client's connecting address; the per-workspace bucket
    keys off a `workspace_id` query parameter when the route carries one.
    Both are best-effort scoping, not an authorization boundary.
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        redis = get_redis()
        category = classify_route(request.url.path)
        rule = rule_for_category(category)

        user_id = request.headers.get(_USER_HEADER) or (
            request.client.host if request.client else "anonymous"
        )
        allowed, _ = await check_sliding_window(redis, f"{category}:user:{user_id}", rule)
        if not allowed:
            return _rate_limited_response(rule.window_seconds)

        workspace_id = request.query_params.get(_WORKSPACE_QUERY_PARAM)
        if workspace_id:
            allowed, _ = await check_sliding_window(
                redis, f"{category}:workspace:{workspace_id}", rule
            )
            if not allowed:
                return _rate_limited_response(rule.window_seconds)

        return await call_next(request)


def _rate_limited_response(retry_after_seconds: int) -> JSONResponse:
    return JSONResponse(
        status_code=429,
        content={"detail": "Rate limit exceeded"},
        headers={"Retry-After": str(retry_after_seconds)},
    )
