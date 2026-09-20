from app.services.ai.tasks.types import AITask

TASK_PROVIDER_POLICY: dict[AITask, tuple[str, ...]] = {
    AITask.RESEARCH: ("perplexity", "gemini"),
    AITask.STRATEGY: ("gemini",),
    AITask.OPPORTUNITY_ANALYSIS: ("gemini",),
    AITask.CONTENT_CONCEPT_GENERATION: ("gemini",),
    AITask.CONTENT_CREATION: ("gemini",),
    AITask.PERFORMANCE_REASONING: ("gemini",),
    AITask.HOOK_GENERATION: ("gemini",),
    AITask.CAPTION_GENERATION: ("gemini",),
    AITask.CONTENT_EVALUATION: ("gemini",),
    AITask.BRAND_ANALYSIS: ("gemini",),
    AITask.AUDIENCE_ANALYSIS: ("gemini",),
    AITask.MARKET_ANALYSIS: ("gemini",),
    AITask.STRATEGIC_SYNTHESIS: ("gemini",),
    AITask.OPPORTUNITY_REASONING: ("gemini",),
    AITask.LEARNING_EXPLANATION: ("gemini",),
}
