from __future__ import annotations

from django.db import transaction

from recommendations.models import Recommendation, UserRecommendation

from gamification.models import UserChallenge
from gamification.services.challenges import update_challenge_progress
from gamification.services.achievements import evaluate_achievements

from django.utils import timezone

class RecommendationActionError(Exception):
    """Raised when a recommendation action cannot be completed."""


@transaction.atomic
def mark_recommendation_completed(
    *,
    user,
    recommendation_id: int,
) -> UserRecommendation:
    """
    Mark one of the authenticated user's ACTIVE recommendations
    as COMPLETED.

    Only ACTIVE recommendations can be completed.
    """

    recommendation = (
        UserRecommendation.objects
        .select_for_update()
        .select_related("recommendation")
        .filter(
            id=recommendation_id,
            user=user,
        )
        .first()
    )

    if recommendation is None:
        raise RecommendationActionError(
            "Recommendation not found."
        )

    if recommendation.status != UserRecommendation.Status.ACTIVE:
        raise RecommendationActionError(
            "Only active recommendations can be completed."
        )

    recommendation.status = UserRecommendation.Status.COMPLETED
    recommendation.save(
        update_fields=["status"]
    )

    if recommendation.recommendation.action_type == (
        Recommendation.ActionType.SUSTAINABILITY
    ):
        active_challenges = (
            UserChallenge.objects
            .filter(
                user=user,
                challenge__is_active=True,
                challenge__start_date__lte=timezone.localdate(),
                challenge__end_date__gte=timezone.localdate(),
                completed=False,
            )
            .select_related("challenge")
        )

        for user_challenge in active_challenges:
            update_challenge_progress(user_challenge)
        evaluate_achievements(user)

    return recommendation


@transaction.atomic
def dismiss_recommendation(
    *,
    user,
    recommendation_id: int,
) -> UserRecommendation:
    """
    Mark one of the authenticated user's ACTIVE recommendations
    as DISMISSED.

    Only ACTIVE recommendations can be dismissed.
    """

    recommendation = (
        UserRecommendation.objects
        .select_for_update()
        .select_related("recommendation")
        .filter(
            id=recommendation_id,
            user=user,
        )
        .first()
    )

    if recommendation is None:
        raise RecommendationActionError(
            "Recommendation not found."
        )

    if recommendation.status != UserRecommendation.Status.ACTIVE:
        raise RecommendationActionError(
            "Only active recommendations can be dismissed."
        )

    recommendation.status = UserRecommendation.Status.DISMISSED
    recommendation.save(
        update_fields=["status"]
    )

    return recommendation