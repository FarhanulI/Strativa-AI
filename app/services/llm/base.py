from typing import Protocol, TypeVar

from pydantic import BaseModel

Result = TypeVar("Result", bound=BaseModel)


class LLMProvider(Protocol):
    async def generate_structured(
        self, *, system_prompt: str, user_prompt: str, response_model: type[Result]
    ) -> Result: ...
