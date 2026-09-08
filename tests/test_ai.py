from pydantic import BaseModel

from app.services.ai.errors import AIProviderRequestError
from app.services.ai.registry import AIModelConfig, ModelRegistry, ProviderRegistry
from app.services.ai.router import AIRouter
from app.services.ai.schemas.requests import AIRequest
from app.services.ai.tasks.types import AICapability, AITask


class Result(BaseModel):
    value: str


class FakeProvider:
    provider = "fake"

    def __init__(self, value: str = "ok", failure: bool = False):
        self.value = value
        self.failure = failure
        self.calls = 0

    async def generate_structured(self, **kwargs: object) -> Result:
        self.calls += 1
        if self.failure:
            raise AIProviderRequestError("provider failed")
        return Result(value=self.value)


def model(provider: str, name: str = "model") -> AIModelConfig:
    return AIModelConfig(
        provider=provider,
        model_name=name,
        capabilities=frozenset({AICapability.TEXT_GENERATION}),
    )


def request(task: AITask = AITask.STRATEGY) -> AIRequest:
    return AIRequest(
        task=task,
        system_prompt="system",
        user_prompt="user",
        response_model=Result,
        required_capabilities={AICapability.TEXT_GENERATION},
    )


def test_model_registry_filters_disabled_and_capabilities() -> None:
    registry = ModelRegistry(
        [model("fake"), AIModelConfig("off", "model", frozenset(), enabled=False)]
    )

    assert registry.find("fake", {AICapability.TEXT_GENERATION}).model_name == "model"


def test_provider_registry_is_lazy_and_caches_provider() -> None:
    instances: list[FakeProvider] = []

    def factory() -> FakeProvider:
        provider = FakeProvider()
        instances.append(provider)
        return provider

    registry = ProviderRegistry()
    registry.register("fake", factory)

    assert instances == []
    assert registry.get("fake") is registry.get("fake")
    assert len(instances) == 1


async def test_router_selects_task_policy_provider() -> None:
    provider = FakeProvider()
    providers = ProviderRegistry()
    providers.register("gemini", lambda: provider)
    router = AIRouter(ModelRegistry([model("gemini")]), providers)

    selection = router.select(request())

    assert selection.provider == "gemini"
    assert selection.model == "model"


async def test_router_falls_back_after_provider_failure() -> None:
    failed = FakeProvider(failure=True)
    fallback = FakeProvider(value="fallback")
    providers = ProviderRegistry()
    providers.register("perplexity", lambda: failed)
    providers.register("gemini", lambda: fallback)
    router = AIRouter(ModelRegistry([model("perplexity"), model("gemini")]), providers)

    result = await router.generate_structured(request(AITask.RESEARCH))

    assert result.output == Result(value="fallback")
    assert result.metadata.provider == "gemini"
    assert failed.calls == 1
    assert fallback.calls == 1