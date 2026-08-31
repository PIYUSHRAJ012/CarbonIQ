from __future__ import annotations

from django.db import transaction

from recommendations.models import UserRecommendation


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