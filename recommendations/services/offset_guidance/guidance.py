from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from recommendations.models import OffsetRecommendation

from .comparison import (
    OffsetProjectComparison,
    build_project_comparison,
)
from .suitability import (
    OffsetSuitability,
    build_offset_suitability,
)
from .verification import (
    OffsetVerification,
    build_offset_verification,
)


REDUCTION_FIRST_MESSAGE = (
    "Reduce avoidable emissions first. Carbon offsets may be "
    "considered as complementary guidance for residual emissions."
)

INFORMATIONAL_GUIDANCE_MESSAGE = (
    "CarbonIQ provides informational guidance. This does not "
    "represent a purchase, retirement, or cancellation instruction."
)


@dataclass(frozen=True)
class OffsetGuidance:
    """
    Unified E9 guidance representation for one persisted
    OffsetRecommendation.
    """

    recommendation_id: int
    project: OffsetProjectComparison
    verification: OffsetVerification
    suitability: OffsetSuitability

    indicative_tonnes: Decimal

    reduction_first_message: str
    informational_message: str


def build_offset_guidance(
    recommendation: OffsetRecommendation,
) -> OffsetGuidance:
    """
    Build the complete E9 guidance representation for one
    persisted OffsetRecommendation.

    This function consumes existing E5 data and delegates all
    interpretation to the E9 guidance services.

    It does not change the recommendation or recalculate its
    historical E5 score.
    """

    comparison = build_project_comparison(
        [recommendation]
    )[0]

    verification = build_offset_verification(
        recommendation.offset_project
    )

    suitability = build_offset_suitability(
        recommendation.offset_project,
        score=recommendation.score,
    )

    return OffsetGuidance(
        recommendation_id=recommendation.id,
        project=comparison,
        verification=verification,
        suitability=suitability,
        indicative_tonnes=recommendation.indicative_tonnes,
        reduction_first_message=REDUCTION_FIRST_MESSAGE,
        informational_message=INFORMATIONAL_GUIDANCE_MESSAGE,
    )


def build_offset_guidance_collection(
    recommendations,
) -> tuple[OffsetGuidance, ...]:
    """
    Build E9 guidance for multiple persisted recommendations.

    The recommendations are first compared/ranked using the
    existing persisted E5 scores.
    """

    comparisons = build_project_comparison(
        recommendations
    )

    recommendation_map = {
        recommendation.id: recommendation
        for recommendation in recommendations
    }

    guidance: list[OffsetGuidance] = []

    for comparison in comparisons:
        recommendation = recommendation_map[
            comparison.recommendation_id
        ]

        verification = build_offset_verification(
            recommendation.offset_project
        )

        suitability = build_offset_suitability(
            recommendation.offset_project,
            score=recommendation.score,
        )

        guidance.append(
            OffsetGuidance(
                recommendation_id=recommendation.id,
                project=comparison,
                verification=verification,
                suitability=suitability,
                indicative_tonnes=(
                    recommendation.indicative_tonnes
                ),
                reduction_first_message=(
                    REDUCTION_FIRST_MESSAGE
                ),
                informational_message=(
                    INFORMATIONAL_GUIDANCE_MESSAGE
                ),
            )
        )

    return tuple(guidance)