class RateLimitDeferredError(Exception):
    """Raised by a job handler when a per-scope rate limit is currently
    exceeded. This is not a job failure: `execute_ai_job` catches it
    separately from a generic handler exception and requeues the job for
    later (without consuming a retry attempt) rather than failing or
    dropping it -- see docs/development/day-18.md "queue excess rather than
    drop".
    """

    def __init__(self, retry_after_seconds: float):
        self.retry_after_seconds = retry_after_seconds
        super().__init__(f"rate limited, retry after {retry_after_seconds}s")
