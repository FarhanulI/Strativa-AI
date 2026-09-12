from collections.abc import Awaitable, Callable
from typing import Any

JobHandler = Callable[[dict[str, Any]], Awaitable[dict[str, Any]]]

_HANDLERS: dict[str, JobHandler] = {}


def register_handler(task_type: str, handler: JobHandler) -> None:
    """Register the coroutine that executes `task_type`. Product days
    (17+) call this once at startup for each real AI task; no product
    handler exists yet, so only the infra-internal echo handler below is
    registered by default.
    """
    _HANDLERS[task_type] = handler


def get_handler(task_type: str) -> JobHandler:
    handler = _HANDLERS.get(task_type)
    if handler is None:
        raise KeyError(f"No job handler registered for task_type '{task_type}'")
    return handler


async def _echo_handler(payload: dict[str, Any]) -> dict[str, Any]:
    """Placeholder handler used only to exercise the job pipeline in tests
    until a real product task type is registered.
    """
    return {"echo": payload}


register_handler("infrastructure.echo", _echo_handler)
