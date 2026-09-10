"""
Scoring utilities for content evaluation.

Handles calculation of overall score from dimension scores
and classification based on thresholds.
"""

from app.models.content_evaluation import EvaluationClassification


# Dimension weights for overall score calculation
DIMENSION_WEIGHTS = {
    "strategic_alignment_score": 0.20,
    "audience_relevance_score": 0.15,
    "hook_strength_score": 0.15,
    "message_clarity_score": 0.10,
    "narrative_coherence_score": 0.10,
    "format_alignment_score": 0.10,
    "emotional_alignment_score": 0.05,
    "cta_alignment_score": 0.05,
    "brand_alignment_score": 0.10,
}

# Classification thresholds
CLASSIFICATION_THRESHOLDS = {
    0.85: EvaluationClassification.EXCELLENT,
    0.70: EvaluationClassification.STRONG,
    0.55: EvaluationClassification.ACCEPTABLE,
    0.40: EvaluationClassification.WEAK,
}


def calculate_overall_score(scores: dict[str, float]) -> float:
    """
    Calculate overall evaluation score from dimension scores.

    The application owns this calculation to ensure consistency.
    Never trust AI-provided overall scores.

    Args:
        scores: Dictionary mapping dimension names to scores (0.0-1.0)

    Returns:
        Weighted overall score (0.0-1.0)

    Raises:
        ValueError: If any required dimension is missing or out of range
    """
    total = 0.0

    for dimension, weight in DIMENSION_WEIGHTS.items():
        if dimension not in scores:
            raise ValueError(f"Missing required dimension score: {dimension}")

        score = scores[dimension]
        if not isinstance(score, (int, float)) or not (0.0 <= score <= 1.0):
            raise ValueError(
                f"Invalid score for {dimension}: {score}. Must be a number between 0.0 and 1.0"
            )

        total += score * weight

    # Round to 2 decimal places for consistency
    return round(total, 2)


def classify_score(overall_score: float) -> EvaluationClassification:
    """
    Classify overall score into a categorical rating.

    Classification is deterministic and application-owned.

    Args:
        overall_score: Overall evaluation score (0.0-1.0)

    Returns:
        EvaluationClassification (excellent, strong, acceptable, weak, or poor)

    Raises:
        ValueError: If score is out of valid range
    """
    if not isinstance(overall_score, (int, float)) or not (0.0 <= overall_score <= 1.0):
        raise ValueError(
            f"Invalid overall score: {overall_score}. Must be a number between 0.0 and 1.0"
        )

    # Check thresholds in descending order
    for threshold in sorted(CLASSIFICATION_THRESHOLDS.keys(), reverse=True):
        if overall_score >= threshold:
            return CLASSIFICATION_THRESHOLDS[threshold]

    # Default to poor if below lowest threshold
    return EvaluationClassification.POOR
