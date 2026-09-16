from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from app.auth.jwt import try_get_request_identity
from app.core.config import settings
from app.infrastructure.ratelimit.limiter import check_sliding_window
from app.infrastructure.ratelimit.policy import classify_route, rule_for_category
from app.infrastructure.redis_client import get_redis

_WORKSPACE_QUERY_PARAM = "workspace_id"


class RateLimitMiddleware(BaseHTTPMiddleware):
    """Redis-backed sliding-window rate limiter, applied per user and per
    workspace, with a lower ceiling for AI-triggering routes than plain CRUD
    routes (see `policy.py`).

    Day 20 note: the per-user bucket now keys off the caller's real JWT
    identity (`app.auth.jwt.try_get_request_identity`) when a valid,
    unexpired access token is presented, falling back to the client's
    connecting address for unauthenticated requests (e.g. the login
    endpoint itself). A client-supplied `X-User-Id` header is no longer
    trusted for identity -- it was never verified and would let a caller
    claim any bucket it likes. The per-workspace bucket still keys off a
    `workspace_id` query parameter when the route carries one; this
    remains best-effort scoping, not an authorization boundary (see
    docs/development/day-20.md for the known ownership-chain gap this
    does not close).
    """

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        if not settings.rate_limit_enabled:
            return await call_next(request)

        redis = get_redis()
        category = classify_route(request.url.path)
        rule = rule_for_category(category)

        user_id = try_get_request_identity(request) or (
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
