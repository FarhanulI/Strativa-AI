from collections.abc import Callable
from dataclasses import dataclass

from app.services.ai.base import StructuredGenerationProvider
from app.services.ai.errors import (
    AICapabilityNotSupportedError,
    AIModelNotAvailableError,
    AIProviderNotConfiguredError,
)
from app.services.ai.tasks.types import AICapability


@dataclass(frozen=True)
class AIModelConfig:
    provider: str
    model_name: str
    capabilities: frozenset[AICapability]
    cost_tier: str = "standard"
    supports_structured_output: bool = False
    supports_vision: bool = False
    supports_web: bool = False
    supports_image_generation: bool = False
    supports_video_generation: bool = False
    supports_audio_generation: bool = False
    enabled: bool = True


class ModelRegistry:
    def __init__(self, models: list[AIModelConfig] | None = None):
        self._models: dict[tuple[str, str], AIModelConfig] = {}
        for model in models or []:
            self.register(model)

    def register(self, model: AIModelConfig) -> None:
        self._models[(model.provider, model.model_name)] = model

    def get(self, provider: str, model_name: str) -> AIModelConfig:
        model = self._models.get((provider, model_name))
        if not model or not model.enabled:
            raise AIModelNotAvailableError(f"AI model is not available: {provider}/{model_name}")
        return model

    def find(self, provider: str, capabilities: set[AICapability]) -> AIModelConfig:
        candidates = [
            model
            for (model_provider, _), model in self._models.items()
            if model_provider == provider
            and model.enabled
            and capabilities <= model.capabilities
        ]
        if not candidates:
            raise AICapabilityNotSupportedError(
                f"No enabled model for provider {provider} supports the requested capabilities"
            )
        return candidates[0]


class ProviderRegistry:
    def __init__(self):
        self._factories: dict[str, Callable[[], StructuredGenerationProvider]] = {}
        self._providers: dict[str, StructuredGenerationProvider] = {}

    def register(self, name: str, factory: Callable[[], StructuredGenerationProvider]) -> None:
        self._factories[name] = factory

    def get(self, name: str) -> StructuredGenerationProvider:
        if name not in self._factories:
            raise AIProviderNotConfiguredError(f"AI provider is not configured: {name}")
        if name not in self._providers:
            self._providers[name] = self._factories[name]()
        return self._providers[name]