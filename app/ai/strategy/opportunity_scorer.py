from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any

from app.models.learning import Learning, LearningDimension, LearningStatus


@dataclass(frozen=True)
class OpportunityScore:
    signal_strength: float
    profile_relevance: float
    goal_alignment: float
    timeliness: float
    # Day 26 feedback-loop-closure factor: a small, capped, additive
    # adjustment (see OpportunityScorer.LEARNING_ALIGNMENT_WEIGHT) applied
    # on top of -- never rebalanced into -- the four core weighted factors
    # above. Defaults to 0.0 whenever no active Learning matches (or none
    # was supplied), so `total` is unchanged from pre-Day-26 behavior in
    # that case.
    learning_alignment: float
    total: float


class OpportunityScorer:
    def calculate_signal_strength(self, signal: Any | None) -> float:
        if signal is None:
            return 0.5
        if hasattr(signal, "strength_score"):
            return self._clamp(signal.strength_score)
        velocity = 0.5 if signal.velocity_score is None else signal.velocity_score
        engagement = 0.5 if signal.engagement_score is None else signal.engagement_score
        return self._clamp((velocity + engagement) * 0.5)

    def calculate_profile_relevance(self, signal: Any | None, profile: Any | None = None) -> float:
        if hasattr(signal, "strength_score"):
            if not signal.topic or profile is None:
                return 0.5
            topic = signal.topic.strip().lower()
            configured = {
                str(value).strip().lower()
                for values in (profile.topics or [], profile.expertise or [])
                for value in values
                if value
            }
            if topic in configured:
                return 1.0
            if any(topic in value or value in topic for value in configured):
                return 0.8
            return 0.5
        if signal is None or signal.relevance_score is None:
            return 0.5
        return self._clamp(signal.relevance_score)

    def calculate_goal_alignment(self, target_objective: str, goals: list[Any] | None) -> float:
        if not goals:
            return 0.5
        configured_goals = {str(goal).lower() for goal in goals}
        return 1.0 if target_objective.lower() in configured_goals else 0.5

    def calculate_timeliness(
        self,
        expires_at: datetime | None,
        detected_at: datetime | None = None,
        now: datetime | None = None,
    ) -> float:
        if expires_at is None:
            return 0.5
        current = now or datetime.now(UTC)
        if expires_at <= current:
            return 0.0
        if detected_at is None:
            return 1.0
        lifetime = (expires_at - detected_at).total_seconds()
        if lifetime <= 0:
            return 0.0
        return self._clamp((expires_at - current).total_seconds() / lifetime)

    # Day 26: the learning_alignment adjustment is intentionally small and
    # non-dominant relative to the four core weighted factors (0.30/0.30/
    # 0.20/0.20 above) -- it can nudge a score, never dominate it.
    LEARNING_ALIGNMENT_WEIGHT = 0.05

    def find_matching_learning(
        self,
        recommended_format: str | None,
        signal_topic: str | None,
        learnings: list[Learning] | None,
    ) -> Learning | None:
        """The active Learning (if any) whose dimension+value matches this
        opportunity's `format` or `topic`, highest-confidence first. Only
        `format`/`topic` are matchable in v1 -- see
        app/learning/extraction.py for why the other LearningDimension
        members have no opportunity-side data to compare against yet.
        """
        if not learnings:
            return None
        candidates = [
            learning
            for learning in learnings
            if learning.status == LearningStatus.ACTIVE
            and (
                (
                    learning.dimension == LearningDimension.FORMAT
                    and recommended_format
                    and learning.dimension_value.lower() == recommended_format.lower()
                )
                or (
                    learning.dimension == LearningDimension.TOPIC
                    and signal_topic
                    and learning.dimension_value.lower() == signal_topic.lower()
                )
            )
        ]
        if not candidates:
            return None
        return max(candidates, key=lambda learning: learning.confidence_level)

    def calculate_learning_alignment(
        self,
        recommended_format: str | None,
        signal_topic: str | None,
        learnings: list[Learning] | None,
    ) -> float:
        matched = self.find_matching_learning(recommended_format, signal_topic, learnings)
        if matched is None:
            return 0.0
        return self._clamp(matched.confidence_level) * self.LEARNING_ALIGNMENT_WEIGHT

    def score(
        self,
        profile: Any,
        signal: Any | None,
        target_objective: str,
        recommended_format: str | None = None,
        learnings: list[Learning] | None = None,
    ) -> OpportunityScore:
        components = {
            "signal_strength": self.calculate_signal_strength(signal),
            "profile_relevance": self.calculate_profile_relevance(signal, profile),
            "goal_alignment": self.calculate_goal_alignment(target_objective, profile.goals),
            "timeliness": self.calculate_timeliness(
                signal.expires_at if signal else None,
                (signal.detected_at if hasattr(signal, "detected_at") else signal.observed_at)
                if signal
                else None,
            ),
        }
        core_total = sum(
            components[name] * weight
            for name, weight in {
                "signal_strength": 0.30,
                "profile_relevance": 0.30,
                "goal_alignment": 0.20,
                "timeliness": 0.20,
            }.items()
        )
        signal_topic = getattr(signal, "topic", None) if signal else None
        learning_alignment = self.calculate_learning_alignment(
            recommended_format, signal_topic, learnings
        )
        total = self._clamp(core_total + learning_alignment)
        return OpportunityScore(**components, learning_alignment=learning_alignment, total=total)

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
