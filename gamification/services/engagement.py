from __future__ import annotations

from dataclasses import dataclass

from gamification.models import Challenge, UserAchievement, UserChallenge
from gamification.services.achievements import (
    AchievementEvaluationResult,
    evaluate_achievements,
)
from gamification.services.score import EcoScore, calculate_eco_score
from django.utils import timezone
from gamification.services.challenges import get_active_challenges

@dataclass(frozen=True)
class EngagementSnapshot:
    """
    Combined gamification state for one CarbonIQ user.

    This object is intentionally read-oriented. Individual services
    remain responsible for their own business rules and persistence.
    """

    eco_score: EcoScore
    earned_achievements: tuple[UserAchievement, ...]
    available_challenges: tuple[Challenge, ...]
    active_challenges: tuple[UserChallenge, ...]
    completed_challenges: tuple[UserChallenge, ...]


@dataclass(frozen=True)
class EngagementRefreshResult:
    """
    Result of explicitly refreshing a user's gamification state.
    """

    snapshot: EngagementSnapshot
    achievement_evaluation: AchievementEvaluationResult


def build_engagement_snapshot(user) -> EngagementSnapshot:
    """
    Build the user's current gamification snapshot.

    No gamification state is created or modified by this function.
    It only reads existing state and calculates the current Eco Score.
    """

    eco_score = calculate_eco_score(user)

    earned_achievements = tuple(
        UserAchievement.objects
        .filter(user=user)
        .select_related("achievement")
        .order_by("-earned_at")
    )

    available_challenges = tuple(
        get_active_challenges()
    )

    today = timezone.localdate()

    active_challenges = tuple(
        UserChallenge.objects
        .filter(
            user=user,
            challenge__is_active=True,
            challenge__start_date__lte=today,
            challenge__end_date__gte=today,
            completed=False,
        )
        .select_related("challenge")
        .order_by(
            "challenge__end_date",
            "challenge__title",
        )
    )

    completed_challenges = tuple(
        UserChallenge.objects
        .filter(
            user=user,
            completed=True,
        )
        .select_related("challenge")
        .order_by("-completed_at")
    )

    return EngagementSnapshot(
        eco_score=eco_score,
        earned_achievements=earned_achievements,
        available_challenges=available_challenges,
        active_challenges=active_challenges,
        completed_challenges=completed_challenges,
    )


def refresh_engagement(user) -> EngagementRefreshResult:
    """
    Explicitly refresh a user's gamification state.

    Achievement evaluation is deliberately explicit rather than being
    triggered as a side effect of a normal dashboard GET request.
    """

    achievement_evaluation = evaluate_achievements(user)

    snapshot = build_engagement_snapshot(user)

    return EngagementRefreshResult(
        snapshot=snapshot,
        achievement_evaluation=achievement_evaluation,
    )