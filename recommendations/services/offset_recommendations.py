from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from recommendations.models import (
    OffsetProject,
    OffsetRecommendation,
)

from .offset_scoring import (
    OffsetRequirement,
    calculate_offset_requirement,
    rank_offset_projects,
)

from .signals import (
    RecommendationSignals,
    build_recommendation_signals,
)


class OffsetRecommendationError(Exception):
    """
    Raised when offset recommendation generation fails safely.
    """


@dataclass(frozen=True)
class GeneratedOffsetRecommendation:
    """
    Result produced for one generated offset recommendation.
    """

    offset_recommendation: OffsetRecommendation
    score: Decimal
    requirement: OffsetRequirement


def _format_source_month(requirement: OffsetRequirement) -> str:
    """
    Return the footprint source month as YYYY-MM.
    """

    source_month = requirement.source_month

    if source_month is None:
        return "the latest completed month"

    if hasattr(source_month, "strftime"):
        return source_month.strftime("%Y-%m")

    return str(source_month)


def _build_reason(
    project: OffsetProject,
    score: Decimal,
    requirement: OffsetRequirement,
) -> str:
    """
    Build a transparent explanation for the recommendation.
    """

    month_label = _format_source_month(requirement)

    return (
        f"Your latest completed carbon footprint for {month_label} "
        f"is {requirement.latest_month_emission_kg:.4f} kg CO2e, "
        f"which corresponds to an indicative offset requirement of "
        f"{requirement.indicative_tonnes:.4f} tonnes CO2e. "
        f"This project received a relevance score of {score:.4f}/100 "
        f"based on footprint-domain relevance, geographic suitability, "
        f"SDG alignment, project type, and available project metadata. "
        f"CarbonIQ presents offsets as supplementary guidance. "
        f"Reducing emissions remains the primary sustainability objective."
    )


def _supersede_active_recommendations(user) -> None:
    """
    Supersede the user's currently active offset recommendations.

    Existing dismissed and completed recommendations are preserved.
    """

    (
        OffsetRecommendation.objects
        .select_for_update()
        .filter(
            user=user,
            status=OffsetRecommendation.Status.ACTIVE,
        )
        .update(
            status=OffsetRecommendation.Status.SUPERSEDED,
        )
    )


def generate_offset_recommendations(
    user,
    *,
    limit: int = 5,
) -> list[GeneratedOffsetRecommendation]:
    """
    Generate personalized offset-project recommendations.

    Flow:

        RecommendationSignals
            -> OffsetRequirement
            -> project scoring
            -> applicability filtering
            -> ranking
            -> persistence

    This service is intentionally separate from the E3
    sustainability-recommendation engine.
    """

    if user is None:
        raise OffsetRecommendationError(
            "A valid user is required to generate offset recommendations."
        )

    if limit <= 0:
        raise OffsetRecommendationError(
            "Recommendation limit must be greater than zero."
        )

    # -------------------------------------------------------------
    # 1. Build CarbonIQ recommendation signals
    # -------------------------------------------------------------
    try:
        signals: RecommendationSignals = build_recommendation_signals(
            user
        )
    except Exception as exc:
        raise OffsetRecommendationError(
            "Unable to build recommendation signals for offset guidance."
        ) from exc

    # -------------------------------------------------------------
    # 2. Calculate indicative offset requirement
    # -------------------------------------------------------------
    try:
        requirement = calculate_offset_requirement(signals)
    except Exception as exc:
        raise OffsetRecommendationError(
            "Unable to calculate the indicative offset requirement."
        ) from exc

    # No completed monthly footprint means there is no safe
    # offset recommendation to generate.
    if requirement is None:
        return []

    # -------------------------------------------------------------
    # 3. Load only currently usable offset projects
    # -------------------------------------------------------------
    projects = list(
        OffsetProject.objects
        .filter(
            is_active=True,
            status="ACTIVE",
        )
        .order_by("id")
    )

    if not projects:
        return []

    # -------------------------------------------------------------
    # 4. Score and rank projects
    # -------------------------------------------------------------
    try:
        ranked_projects = rank_offset_projects(
            projects,
            signals,
            user,
        )
    except Exception as exc:
        raise OffsetRecommendationError(
            "Unable to rank available offset projects."
        ) from exc

    # Keep only projects considered applicable by the E5 scoring layer.
    applicable_projects = [
        result
        for result in ranked_projects
        if result.applicable
    ]

    selected_projects = applicable_projects[:limit]

    if not selected_projects:
        return []

    # -------------------------------------------------------------
    # 5. Persist atomically
    # -------------------------------------------------------------
    with transaction.atomic():
        _supersede_active_recommendations(user)

        generated: list[GeneratedOffsetRecommendation] = []

        for result in selected_projects:
            project = result.project

            score = Decimal(
                str(result.score)
            ).quantize(
                Decimal("0.0001")
            )

            recommendation = OffsetRecommendation.objects.create(
                user=user,
                offset_project=project,
                score=score,
                reason=_build_reason(
                    project=project,
                    score=score,
                    requirement=requirement,
                ),
                indicative_tonnes=requirement.indicative_tonnes,
                status=OffsetRecommendation.Status.ACTIVE,
            )

            generated.append(
                GeneratedOffsetRecommendation(
                    offset_recommendation=recommendation,
                    score=score,
                    requirement=requirement,
                )
            )

    return generated