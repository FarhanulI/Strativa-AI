from collections.abc import Awaitable
from typing import Protocol, TypeVar

from pydantic import BaseModel

Result = TypeVar("Result", bound=BaseModel)


class StructuredGenerationProvider(Protocol):
    provider: str

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[Result],
        model: str | None = None,
        temperature: float | None = None,
    ) -> Result: ...


class ImageGenerationProvider(Protocol):
    def generate_image(self, *args: object, **kwargs: object) -> Awaitable[object]: ...


class VideoGenerationProvider(Protocol):
    def generate_video(self, *args: object, **kwargs: object) -> Awaitable[object]: ...


class AudioGenerationProvider(Protocol):
    def generate_audio(self, *args: object, **kwargs: object) -> Awaitable[object]: ...


AIProvider = StructuredGenerationProvider