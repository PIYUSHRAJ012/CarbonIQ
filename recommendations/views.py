from django.contrib.auth.decorators import login_required

from django.contrib import messages
from django.shortcuts import redirect, render

from .models import (
    OffsetRecommendation,
    Recommendation,
    UserRecommendation,
)
from .services.actions import (
    RecommendationActionError,
    dismiss_recommendation,
    mark_recommendation_completed,
)
from .services.offset_guidance.guidance import (
    build_offset_guidance_collection,
)


@login_required
def recommendations(request):
    """
    Display the authenticated user's active personalized
    recommendations and expanded E9 offset guidance.
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

    # Keep the existing E3 offset recommendation section intact.
    #
    # These are UserRecommendation records and are intentionally
    # separate from the E5 OffsetRecommendation model.
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

    # -------------------------------------------------------------
    # E9: Expanded offset-project guidance
    # -------------------------------------------------------------
    #
    # Query ONLY the authenticated user's own OffsetRecommendation
    # records. This preserves user isolation.
    #
    # No recommendation generation happens here. The view only
    # presents already-persisted E5 recommendations through the
    # E9 guidance layer.
    #
    # Keeping generation out of the view also prevents page loads
    # from unexpectedly modifying recommendation state.
    e5_offset_recommendations = (
        OffsetRecommendation.objects
        .filter(
            user=request.user,
            status=OffsetRecommendation.Status.ACTIVE,
        )
        .select_related(
            "offset_project",
        )
        .order_by(
            "-score",
            "-generated_at",
            "offset_project__name",
        )
    )

    offset_guidance = build_offset_guidance_collection(
        e5_offset_recommendations
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
            "offset_guidance": offset_guidance,
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