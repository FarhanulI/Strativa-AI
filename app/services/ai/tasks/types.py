from enum import StrEnum


class AITask(StrEnum):
    RESEARCH = "research"
    STRATEGY = "strategy"
    OPPORTUNITY_ANALYSIS = "opportunity_analysis"
    CONTENT_CONCEPT_GENERATION = "content_concept_generation"
    CONTENT_CREATION = "content_creation"
    PERFORMANCE_REASONING = "performance_reasoning"
    HOOK_GENERATION = "hook_generation"
    CAPTION_GENERATION = "caption_generation"
    CONTENT_EVALUATION = "content_evaluation"
    BRAND_ANALYSIS = "brand_analysis"
    AUDIENCE_ANALYSIS = "audience_analysis"
    MARKET_ANALYSIS = "market_analysis"
    STRATEGIC_SYNTHESIS = "strategic_synthesis"


class AICapability(StrEnum):
    TEXT_GENERATION = "text_generation"
    REASONING = "reasoning"
    STRUCTURED_OUTPUT = "structured_output"
    WEB_RESEARCH = "web_research"
    IMAGE_UNDERSTANDING = "image_understanding"
    IMAGE_GENERATION = "image_generation"
    VIDEO_UNDERSTANDING = "video_understanding"
    VIDEO_GENERATION = "video_generation"
    AUDIO_GENERATION = "audio_generation"
    LONG_CONTEXT = "long_context"
