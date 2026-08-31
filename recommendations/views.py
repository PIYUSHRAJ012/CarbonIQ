from django.contrib.auth.decorators import login_required

from django.contrib import messages
from django.shortcuts import get_object_or_404, redirect, render

from .models import Recommendation, UserRecommendation
from .services.actions import (
    RecommendationActionError,
    dismiss_recommendation,
    mark_recommendation_completed,
)

@login_required
def recommendations(request):
    """
    Display the authenticated user's active personalized
    recommendations.
    """

    sustainability_recommendations = (
        UserRecommendation.objects
        .filter(
            user=request.user,
            status=UserRecommendation.Status.ACTIVE,
            recommendation__action_type=(
                Recommendation.ActionType.SUSTAINABILITY
            ),
        )
        .select_related(
            "recommendation",
            "recommendation__category",
        )
        .order_by(
            "-score",
            "-generated_at",
            "recommendation__title",
        )
    )

    offset_recommendations = (
        UserRecommendation.objects
        .filter(
            user=request.user,
            status=UserRecommendation.Status.ACTIVE,
            recommendation__action_type=(
                Recommendation.ActionType.OFFSET
            ),
        )
        .select_related(
            "recommendation",
            "recommendation__category",
        )
        .order_by(
            "-score",
            "-generated_at",
            "recommendation__title",
        )
    )

    return render(
        request,
        "recommendations/list.html",
        {
            "sustainability_recommendations": (
                sustainability_recommendations
            ),
            "offset_recommendations": (
                offset_recommendations
            ),
        },
    )

@login_required
def complete_recommendation(request, recommendation_id):
    """
    Mark one active recommendation as completed.
    """

    if request.method != "POST":
        return redirect("recommendations:list")

    try:
        mark_recommendation_completed(
            user=request.user,
            recommendation_id=recommendation_id,
        )
        messages.success(
            request,
            "Recommendation marked as completed.",
        )

    except RecommendationActionError:
        messages.error(
            request,
            "This recommendation could not be completed.",
        )

    return redirect("recommendations:list")


@login_required
def dismiss(request, recommendation_id):
    """
    Dismiss one active recommendation.
    """

    if request.method != "POST":
        return redirect("recommendations:list")

    try:
        dismiss_recommendation(
            user=request.user,
            recommendation_id=recommendation_id,
        )
        messages.success(
            request,
            "Recommendation dismissed.",
        )

    except RecommendationActionError:
        messages.error(
            request,
            "This recommendation could not be dismissed.",
        )

    return redirect("recommendations:list")