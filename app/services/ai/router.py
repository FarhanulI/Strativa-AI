import time
from dataclasses import dataclass

from pydantic import BaseModel

from app.core.config import settings
from app.services.ai.base import StructuredGenerationProvider
from app.services.ai.errors import AIError, AIProviderUnavailableError
from app.services.ai.policies import TASK_PROVIDER_POLICY
from app.services.ai.providers.gemini import GeminiProvider
from app.services.ai.registry import AIModelConfig, ModelRegistry, ProviderRegistry
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.schemas.responses import AIResponseMetadata
from app.services.ai.tasks.types import AICapability


@dataclass(frozen=True)
class AISelection:
    provider: str
    model: str


@dataclass(frozen=True)
class AIResult:
    output: BaseModel
    metadata: AIResponseMetadata


def default_model_registry() -> ModelRegistry:
    return ModelRegistry(
        [
            AIModelConfig(
                provider="gemini",
                model_name=settings.llm_model,
                capabilities=frozenset(
                    {
                        AICapability.TEXT_GENERATION,
                        AICapability.REASONING,
                        AICapability.STRUCTURED_OUTPUT,
                        AICapability.IMAGE_UNDERSTANDING,
                        AICapability.VIDEO_UNDERSTANDING,
                        AICapability.LONG_CONTEXT,
                    }
                ),
                supports_structured_output=True,
                supports_vision=True,
            )
        ]
    )


def default_provider_registry() -> ProviderRegistry:
    registry = ProviderRegistry()
    registry.register("gemini", GeminiProvider)
    return registry


class AIRouter:
    def __init__(
        self,
        model_registry: ModelRegistry | None = None,
        provider_registry: ProviderRegistry | None = None,
    ):
        self.models = model_registry or default_model_registry()
        self.providers = provider_registry or default_provider_registry()

    def select(self, request: AIRequest) -> AISelection:
        for provider_name in self._provider_candidates(request):
            try:
                model = self._model_for(provider_name, request)
                return AISelection(provider_name, model.model_name)
            except AIError:
                continue
        raise AIProviderUnavailableError(f"No available provider for task {request.task}")

    async def generate_structured(self, request: AIRequest) -> AIResult:
        if request.response_model is None:
            raise ValueError("A response_model is required for structured generation")
        last_error: AIError | None = None
        for provider_name in self._provider_candidates(request):
            try:
                model = self._model_for(provider_name, request)
                provider: StructuredGenerationProvider = self.providers.get(provider_name)
                started = time.perf_counter()
                output = await provider.generate_structured(
                    system_prompt=request.system_prompt,
                    user_prompt=request.user_prompt,
                    response_model=request.response_model,
                    model=model.model_name,
                    temperature=request.temperature,
                )
                metadata = AIResponseMetadata(
                    provider=provider_name,
                    model=model.model_name,
                    latency_ms=round((time.perf_counter() - started) * 1000),
                )
                return AIResult(output=output, metadata=metadata)
            except AIError as error:
                last_error = error
        raise AIProviderUnavailableError(
            f"All providers failed for task {request.task}"
        ) from last_error

    def _provider_candidates(self, request: AIRequest) -> tuple[str, ...]:
        policy = TASK_PROVIDER_POLICY.get(request.task, ())
        if request.preferred_provider:
            return (request.preferred_provider,) + tuple(
                name for name in policy if name != request.preferred_provider
            )
        return policy

    def _model_for(self, provider_name: str, request: AIRequest) -> AIModelConfig:
        if request.preferred_model and provider_name == request.preferred_provider:
            return self.models.get(provider_name, request.preferred_model)
        return self.models.find(provider_name, request.required_capabilities)