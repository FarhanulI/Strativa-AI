from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Any


@dataclass(frozen=True)
class OpportunityScore:
    signal_strength: float
    profile_relevance: float
    goal_alignment: float
    timeliness: float
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

    def score(self, profile: Any, signal: Any | None, target_objective: str) -> OpportunityScore:
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
        total = sum(
            components[name] * weight
            for name, weight in {
                "signal_strength": 0.30,
                "profile_relevance": 0.30,
                "goal_alignment": 0.20,
                "timeliness": 0.20,
            }.items()
        )
        return OpportunityScore(**components, total=self._clamp(total))

    @staticmethod
    def _clamp(value: float) -> float:
        return max(0.0, min(1.0, value))
