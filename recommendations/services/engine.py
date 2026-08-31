from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from recommendations.models import Recommendation, UserRecommendation
from recommendations.services.scoring import RecommendationScore, rank_recommendations
from recommendations.services.signals import (
    RecommendationSignals,
    build_recommendation_signals,
)


MAX_SUSTAINABILITY_RECOMMENDATIONS = 5
MAX_OFFSET_RECOMMENDATIONS = 2


class RecommendationEngineError(Exception):
    """
    Raised when personalized recommendation generation fails.
    """


@dataclass(frozen=True)
class GeneratedRecommendation:
    """
    Represents a persisted personalized recommendation.
    """

    user_recommendation: UserRecommendation
    score: RecommendationScore


def _category_percentage(
    category_emission: Decimal,
    total_emission: Decimal,
) -> Decimal | None:
    """
    Return a category's percentage contribution to total emissions.
    """

    if total_emission <= Decimal("0"):
        return None

    return (
        category_emission
        / total_emission
        * Decimal("100")
    )


def _get_category_emission(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> Decimal | None:
    """
    Return observed emissions for the recommendation's category.
    """

    if recommendation.category is None:
        return None

    category_name = recommendation.category.name

    for row in signals.category_emissions:
        if row.get("category__name") != category_name:
            continue

        value = row.get("total_emission")

        if value is None:
            return None

        return Decimal(str(value))

    return None


def _build_reason(
    scored: RecommendationScore,
    signals: RecommendationSignals,
) -> str:
    """
    Build an explainable reason for a personalized recommendation.

    The reason only uses signals that are actually available.
    """

    recommendation = scored.recommendation

    if recommendation.action_type == Recommendation.ActionType.OFFSET:
        return (
            "Carbon offsets are presented as a complementary option "
            "for residual emissions after practical emission-reduction "
            "actions have been considered."
        )

    reasons: list[str] = []

    category_emission = _get_category_emission(
        recommendation,
        signals,
    )

    if (
        category_emission is not None
        and signals.total_emission > Decimal("0")
    ):
        percentage = _category_percentage(
            category_emission,
            signals.total_emission,
        )

        if percentage is not None:
            reasons.append(
                f"{recommendation.category.name} contributes "
                f"{percentage.quantize(Decimal('0.1'))}% "
                "of your current carbon footprint."
            )

    if scored.trend_score > Decimal("60"):
        reasons.append(
            "Your recent emissions show an increasing trend."
        )
    elif scored.trend_score < Decimal("40"):
        reasons.append(
            "Your recent emissions show a decreasing trend."
        )

    if (
        signals.rf_prediction is not None
        and scored.rf_score > Decimal("60")
    ):
        reasons.append(
            "Your predicted next-month footprint is higher than "
            "your latest observed footprint."
        )

    if (
        signals.user_segment
        and scored.segment_score >= Decimal("75")
    ):
        reasons.append(
            f"Your current behavioral profile is "
            f"{signals.user_segment}."
        )

    if not reasons:
        reasons.append(
            "This recommendation is relevant to your current "
            "CarbonIQ activity profile."
        )

    return " ".join(reasons)


def _select_recommendations(
    ranked_results: list[RecommendationScore],
) -> list[RecommendationScore]:
    """
    Select a focused recommendation set.

    Up to five sustainability actions and two offset suggestions
    are returned.
    """

    sustainability = [
        result
        for result in ranked_results
        if (
            result.applicable
            and result.recommendation.action_type
            == Recommendation.ActionType.SUSTAINABILITY
        )
    ]

    offsets = [
        result
        for result in ranked_results
        if (
            result.applicable
            and result.recommendation.action_type
            == Recommendation.ActionType.OFFSET
        )
    ]

    return (
        sustainability[:MAX_SUSTAINABILITY_RECOMMENDATIONS]
        + offsets[:MAX_OFFSET_RECOMMENDATIONS]
    )


@transaction.atomic
def generate_user_recommendations(
    user,
) -> list[GeneratedRecommendation]:
    """
    Generate and persist personalized recommendations for one user.

    The operation is atomic:
    - previous ACTIVE recommendations become SUPERSEDED
    - the new recommendation set is created

    If anything fails, the transaction is rolled back.
    """

    try:
        signals = build_recommendation_signals(user)

        active_recommendations = (
            Recommendation.objects
            .filter(is_active=True)
            .select_related("category")
        )

        ranked_results = rank_recommendations(
            active_recommendations,
            signals,
        )

        selected_results = _select_recommendations(
            ranked_results
        )

        UserRecommendation.objects.filter(
            user=user,
            status=UserRecommendation.Status.ACTIVE,
        ).update(
            status=UserRecommendation.Status.SUPERSEDED
        )

        generated_results: list[GeneratedRecommendation] = []

        for scored in selected_results:
            user_recommendation = UserRecommendation.objects.create(
                user=user,
                recommendation=scored.recommendation,
                score=scored.score,
                reason=_build_reason(
                    scored,
                    signals,
                ),
                status=UserRecommendation.Status.ACTIVE,
            )

            generated_results.append(
                GeneratedRecommendation(
                    user_recommendation=user_recommendation,
                    score=scored,
                )
            )

        return generated_results

    except RecommendationEngineError:
        raise

    except Exception as exc:
        raise RecommendationEngineError(
            "Failed to generate personalized recommendations."
        ) from exc