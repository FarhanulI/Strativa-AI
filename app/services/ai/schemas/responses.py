from pydantic import BaseModel


class AIResponseMetadata(BaseModel):
    provider: str
    model: str
    latency_ms: int | None = None
    input_tokens: int | None = None
    output_tokens: int | None = None
    total_tokens: int | None = None