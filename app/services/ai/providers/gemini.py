import json
from typing import Any

from pydantic import BaseModel, ValidationError

from app.core.config import settings
from app.services.ai.errors import (
    AIProviderNotConfiguredError,
    AIProviderRequestError,
    AIStructuredOutputError,
)


class GeminiProvider:
    provider = "gemini"

    def __init__(self, client: Any | None = None):
        self._client = client

    async def generate_structured(
        self,
        *,
        system_prompt: str,
        user_prompt: str,
        response_model: type[BaseModel],
        model: str | None = None,
        temperature: float | None = None,
    ) -> BaseModel:
        if not settings.gemini_api_key:
            raise AIProviderNotConfiguredError("Gemini provider is not configured")
        client = self._client or self._create_client()
        try:
            from google.genai import types

            config = types.GenerateContentConfig(
                system_instruction=system_prompt,
                response_mime_type="application/json",
                response_schema=response_model,
                temperature=temperature,
            )
            response = await client.aio.models.generate_content(
                model=model or settings.llm_model,
                contents=user_prompt,
                config=config,
            )
        except Exception as error:
            raise AIProviderRequestError("Gemini request failed") from error

        try:
            parsed = getattr(response, "parsed", None)
            if isinstance(parsed, response_model):
                return parsed
            if parsed is not None:
                return response_model.model_validate(parsed)
            text = getattr(response, "text", None)
            if not text:
                raise AIStructuredOutputError("Gemini returned an empty response")
            return response_model.model_validate(json.loads(text))
        except (ValidationError, json.JSONDecodeError, TypeError) as error:
            raise AIStructuredOutputError("Gemini returned invalid structured output") from error

    @staticmethod
    def _create_client() -> Any:
        try:
            from google import genai

            return genai.Client(api_key=settings.gemini_api_key)
        except Exception as error:
            raise AIProviderRequestError("Gemini client could not be initialized") from error