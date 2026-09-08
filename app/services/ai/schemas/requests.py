from pydantic import BaseModel, ConfigDict, Field

from app.services.ai.tasks.types import AICapability, AITask


class AIRequest(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    task: AITask
    system_prompt: str
    user_prompt: str
    response_model: type[BaseModel] | None = None
    required_capabilities: set[AICapability] = Field(default_factory=set)
    preferred_provider: str | None = None
    preferred_model: str | None = None
    quality_requirement: str = "standard"
    cost_requirement: str = "standard"
    latency_requirement: str = "standard"
    temperature: float | None = None