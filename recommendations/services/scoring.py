from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from recommendations.models import Recommendation
from recommendations.services.signals import RecommendationSignals


# ---------------------------------------------------------------------------
# Scoring weights
# ---------------------------------------------------------------------------

BASE_PRIORITY_WEIGHT = Decimal("0.10")
CATEGORY_WEIGHT = Decimal("0.30")
TREND_WEIGHT = Decimal("0.20")
RF_WEIGHT = Decimal("0.20")
SEGMENT_WEIGHT = Decimal("0.20")

# Trend and RF prediction changes are normalized over this range.
CHANGE_MIN_PERCENT = Decimal("-50")
CHANGE_MAX_PERCENT = Decimal("50")

# Offset recommendations are intentionally secondary to emission-reduction
# recommendations.
OFFSET_SCORE_CEILING = Decimal("60")


# ---------------------------------------------------------------------------
# Category → interpreted K-Means domain mapping
# ---------------------------------------------------------------------------

CATEGORY_DOMAIN_MAP = {
    "Electricity": "energy",
    "Transportation": "transport",
    "Petrol": "transport",
    "Diesel": "transport",
    "Rice & Grain": "food",
    "Legumes": "food",
    "Milk": "food",
    "Tofu": "food",
    "Fruit": "food",
    "Vegetables": "food",
    "Clothing": "shopping",
    "Footwear": "shopping",
    "Waste": "waste",
}


@dataclass(frozen=True)
class RecommendationScore:
    """
    Complete scoring result for one recommendation.
    """

    recommendation: Recommendation

    score: Decimal

    base_priority_score: Decimal
    category_score: Decimal
    trend_score: Decimal
    rf_score: Decimal
    segment_score: Decimal

    applicable: bool


# ---------------------------------------------------------------------------
# Generic helpers
# ---------------------------------------------------------------------------

def clamp(
    value: Decimal,
    minimum: Decimal = Decimal("0"),
    maximum: Decimal = Decimal("100"),
) -> Decimal:
    """
    Keep a Decimal value inside the requested range.
    """

    return max(minimum, min(value, maximum))


def normalize_percentage_change(
    change_percent: Decimal,
) -> Decimal:
    """
    Convert a percentage change in the range [-50%, +50%] into a 0–100 score.

    -50% → 0
      0% → 50
    +50% → 100
    """

    change_percent = clamp(
        change_percent,
        CHANGE_MIN_PERCENT,
        CHANGE_MAX_PERCENT,
    )

    normalized = (
        (
            change_percent - CHANGE_MIN_PERCENT
        )
        / (
            CHANGE_MAX_PERCENT - CHANGE_MIN_PERCENT
        )
    ) * Decimal("100")

    return clamp(normalized)


def get_category_name(recommendation: Recommendation) -> str | None:
    """
    Return the linked CarbonIQ activity category name.
    """

    if recommendation.category is None:
        return None

    return recommendation.category.name


def get_category_domain(
    recommendation: Recommendation,
) -> str | None:
    """
    Convert a CarbonIQ activity category into the semantic domain used by
    the interpreted K-Means profile.
    """

    category_name = get_category_name(recommendation)

    if category_name is None:
        return None

    return CATEGORY_DOMAIN_MAP.get(category_name)


# ---------------------------------------------------------------------------
# Base priority
# ---------------------------------------------------------------------------

def calculate_base_priority_score(
    recommendation: Recommendation,
) -> Decimal:
    """
    Convert catalog priority into the normalized 0–100 base score.
    """

    return clamp(
        Decimal(recommendation.priority)
    )


# ---------------------------------------------------------------------------
# Category relevance
# ---------------------------------------------------------------------------

def calculate_category_score(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Score how strongly the recommendation's category contributes to the
    user's observed carbon footprint.

    Category-specific recommendations use:

        category emission / total emission * 100

    Category-independent recommendations receive a neutral score.
    """

    category_name = get_category_name(recommendation)

    if category_name is None:
        return Decimal("50")

    total_emission = signals.total_emission

    if total_emission <= Decimal("0"):
        return Decimal("50")

    for row in signals.category_emissions:
        if row.get("category__name") != category_name:
            continue

        category_emission = row.get("total_emission")

        if category_emission is None:
            return Decimal("0")

        category_emission = Decimal(str(category_emission))

        score = (
            category_emission
            / total_emission
        ) * Decimal("100")

        return clamp(score)

    # No observed emissions for this category.
    return Decimal("0")


# ---------------------------------------------------------------------------
# Trend relevance
# ---------------------------------------------------------------------------

def _get_latest_two_months(
    signals: RecommendationSignals,
) -> tuple[dict, dict] | None:
    """
    Return the previous and latest monthly records when at least two
    observations exist.
    """

    if len(signals.monthly_emissions) < 2:
        return None

    ordered = sorted(
        signals.monthly_emissions,
        key=lambda row: row["month"],
    )

    return ordered[-2], ordered[-1]


def calculate_trend_score(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Calculate a category trend score.

    If fewer than two monthly observations exist, return a neutral score.

    For category-specific recommendations, the calculation currently uses
    the category's total monthly contribution when that historical detail
    is available. The existing analytics contract only exposes total monthly
    emissions, so without category-by-month history we use the overall user
    trend as the reliable signal.

    Category-independent offset recommendations receive a neutral value.
    """

    if recommendation.action_type == Recommendation.ActionType.OFFSET:
        return Decimal("50")

    latest_two = _get_latest_two_months(signals)

    if latest_two is None:
        return Decimal("50")

    previous, latest = latest_two

    previous_value = Decimal(
        str(previous.get("total_emission", 0))
    )
    latest_value = Decimal(
        str(latest.get("total_emission", 0))
    )

    if previous_value <= Decimal("0"):
        return Decimal("50")

    change_percent = (
        (latest_value - previous_value)
        / previous_value
    ) * Decimal("100")

    return normalize_percentage_change(change_percent)


# ---------------------------------------------------------------------------
# Random Forest signal
# ---------------------------------------------------------------------------

def calculate_rf_score(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Convert Random Forest next-month prediction into a 0–100 signal.

    The score reflects the predicted change relative to the latest observed
    total footprint.

    When RF is unavailable, use a neutral score of 50.
    """

    if recommendation.action_type == Recommendation.ActionType.OFFSET:
        return Decimal("50")

    if signals.rf_prediction is None:
        return Decimal("50")

    current_emission = signals.total_emission

    if current_emission <= Decimal("0"):
        return Decimal("50")

    predicted_emission = Decimal(
        str(signals.rf_prediction)
    )

    if predicted_emission < Decimal("0"):
        return Decimal("50")

    change_percent = (
        (predicted_emission - current_emission)
        / current_emission
    ) * Decimal("100")

    return normalize_percentage_change(change_percent)


# ---------------------------------------------------------------------------
# K-Means segment relevance
# ---------------------------------------------------------------------------

def calculate_segment_score(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Calculate recommendation relevance using the interpreted K-Means
    semantic domain profile.

    If K-Means is unavailable, return a neutral score.
    """

    if recommendation.action_type == Recommendation.ActionType.OFFSET:
        return Decimal("50")

    if not signals.segment_domain_scores:
        return Decimal("50")

    recommendation_domain = get_category_domain(
        recommendation
    )

    if recommendation_domain is None:
        return Decimal("50")

    domain_scores = signals.segment_domain_scores

    if recommendation_domain not in domain_scores:
        return Decimal("0")

    relevant_score = Decimal(
        str(domain_scores[recommendation_domain])
    )

    if relevant_score < Decimal("0"):
        return Decimal("0")

    maximum_score = max(
        (
            Decimal(str(value))
            for value in domain_scores.values()
        ),
        default=Decimal("0"),
    )

    if maximum_score <= Decimal("0"):
        return Decimal("50")

    score = (
        relevant_score / maximum_score
    ) * Decimal("100")

    return clamp(score)


# ---------------------------------------------------------------------------
# Applicability
# ---------------------------------------------------------------------------

def is_recommendation_applicable(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> bool:
    """
    Determine whether a recommendation should be considered for this user.

    Category-specific sustainability recommendations require observed
    activity in that category.

    Offset recommendations are category-independent and remain applicable
    when the user has a non-zero footprint.
    """

    if not recommendation.is_active:
        return False

    if recommendation.action_type == Recommendation.ActionType.OFFSET:
        return signals.total_emission > Decimal("0")

    category_name = get_category_name(recommendation)

    if category_name is None:
        return True

    return any(
        row.get("category__name") == category_name
        and Decimal(
            str(row.get("total_emission", 0))
        ) > Decimal("0")
        for row in signals.category_emissions
    )


# ---------------------------------------------------------------------------
# Final score
# ---------------------------------------------------------------------------

def calculate_recommendation_score(
    recommendation: Recommendation,
    signals: RecommendationSignals,
) -> RecommendationScore:
    """
    Calculate the complete personalized relevance score.
    """

    applicable = is_recommendation_applicable(
        recommendation,
        signals,
    )

    base_priority_score = (
        calculate_base_priority_score(
            recommendation
        )
    )

    category_score = calculate_category_score(
        recommendation,
        signals,
    )

    trend_score = calculate_trend_score(
        recommendation,
        signals,
    )

    rf_score = calculate_rf_score(
        recommendation,
        signals,
    )

    segment_score = calculate_segment_score(
        recommendation,
        signals,
    )

    score = (
        (
            base_priority_score
            * BASE_PRIORITY_WEIGHT
        )
        + (
            category_score
            * CATEGORY_WEIGHT
        )
        + (
            trend_score
            * TREND_WEIGHT
        )
        + (
            rf_score
            * RF_WEIGHT
        )
        + (
            segment_score
            * SEGMENT_WEIGHT
        )
    )

    score = clamp(score)

    if recommendation.action_type == Recommendation.ActionType.OFFSET:
        score = min(
            score,
            OFFSET_SCORE_CEILING,
        )

    if not applicable:
        score = Decimal("0")

    return RecommendationScore(
        recommendation=recommendation,
        score=score.quantize(
            Decimal("0.0001")
        ),
        base_priority_score=base_priority_score,
        category_score=category_score,
        trend_score=trend_score,
        rf_score=rf_score,
        segment_score=segment_score,
        applicable=applicable,
    )


# ---------------------------------------------------------------------------
# Ranking
# ---------------------------------------------------------------------------

def rank_recommendations(
    recommendations: Iterable[Recommendation],
    signals: RecommendationSignals,
) -> list[RecommendationScore]:
    """
    Score and rank a collection of active recommendations.

    Tie-breaking:
        1. Higher final score
        2. Higher category score
        3. Higher base priority
        4. Alphabetical title
    """

    scored = [
        calculate_recommendation_score(
            recommendation,
            signals,
        )
        for recommendation in recommendations
    ]

    return sorted(
        scored,
        key=lambda result: (
            -result.score,
            -result.category_score,
            -result.base_priority_score,
            result.recommendation.title.lower(),
        ),
    )