from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

from analytics.services.aggregation import AnalyticsAggregationService
from carbon.services.comparison import get_user_monthly_benchmark_comparison
from recommendations.models import (
    Recommendation,
    UserRecommendation,
)

ZERO = Decimal("0")
FIFTY = Decimal("50")
HUNDRED = Decimal("100")

EMISSION_PERFORMANCE_WEIGHT = Decimal("0.40")
IMPROVEMENT_TREND_WEIGHT = Decimal("0.25")
SUSTAINABLE_BEHAVIOUR_WEIGHT = Decimal("0.20")
ENGAGEMENT_PROGRESS_WEIGHT = Decimal("0.15")

SCORE_QUANTIZE = Decimal("0.01")


@dataclass(frozen=True)
class EcoScore:
    """
    Complete Eco Score result for one CarbonIQ user.

    All component values and the final score are normalized to 0–100.
    """

    overall_score: Decimal
    emission_performance: Decimal
    improvement_trend: Decimal
    sustainable_behaviour: Decimal
    engagement_progress: Decimal


def _clamp(
    value: Decimal,
    minimum: Decimal = ZERO,
    maximum: Decimal = HUNDRED,
) -> Decimal:
    """
    Keep a Decimal value inside the requested range.
    """

    return max(minimum, min(value, maximum))


def _round_score(value: Decimal) -> Decimal:
    """
    Normalize score precision for deterministic application output.
    """

    return _clamp(value).quantize(
        SCORE_QUANTIZE,
        rounding=ROUND_HALF_UP,
    )


def _get_latest_monthly_emission(user) -> Decimal | None:
    """
    Return the user's latest completed monthly footprint.

    Returns None when the user has no completed footprint data.
    """

    monthly_emissions = list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )

    if not monthly_emissions:
        return None

    latest = max(
        monthly_emissions,
        key=lambda row: row["month"],
    )

    value = latest.get("total_emission")

    if value is None:
        return None

    return Decimal(str(value))


def _calculate_emission_performance(user) -> Decimal:
    """
    Score the latest monthly footprint against the user's
    resolved E4 benchmark.

    The benchmark is the normalized monthly kg CO2e/person value
    already provided by CarbonIQ's benchmarking service.

    Scoring model:

        score = 100 - 50 * (personal / benchmark)

    Therefore:

        0x benchmark   -> 100
        0.5x           -> 75
        1.0x           -> 50
        1.5x           -> 25
        2.0x or more   -> 0

    When benchmark or footprint data is unavailable, a neutral
    score of 50 is returned rather than penalizing a cold-start user.
    """

    latest_emission = _get_latest_monthly_emission(user)

    if latest_emission is None or latest_emission <= ZERO:
        return FIFTY if latest_emission is None else HUNDRED

    try:
        benchmark_comparison = get_user_monthly_benchmark_comparison(
            user
        )
    except ValueError:
        return FIFTY

    benchmark = benchmark_comparison.benchmark_monthly_kg

    if benchmark is None or benchmark <= ZERO:
        return FIFTY

    score = (
        HUNDRED
        - (
            Decimal("50")
            * latest_emission
            / benchmark
        )
    )

    return _round_score(score)


def _calculate_improvement_trend(user) -> Decimal:
    """
    Score the change between the two latest completed months.

    A 50% reduction produces 100.
    No change produces 50.
    A 50% increase produces 0.

    Values beyond that range are clamped.

    With fewer than two completed months, return a neutral 50.
    """

    monthly_emissions = list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )

    if len(monthly_emissions) < 2:
        return FIFTY

    ordered = sorted(
        monthly_emissions,
        key=lambda row: row["month"],
    )

    previous = Decimal(
        str(ordered[-2]["total_emission"])
    )

    latest = Decimal(
        str(ordered[-1]["total_emission"])
    )

    if previous <= ZERO:
        return FIFTY

    change_percent = (
        (latest - previous)
        / previous
        * HUNDRED
    )

    score = FIFTY - change_percent

    return _round_score(score)


def _calculate_sustainable_behaviour(user) -> Decimal:
    """
    Score completion of sustainability recommendations that were
    actually issued to the user.

    Offset recommendations are intentionally excluded because E8
    measures reduction-oriented sustainable behaviour.

    With no sustainability recommendations issued, return a neutral
    score of 50.
    """

    recommendations = UserRecommendation.objects.filter(
        user=user,
        recommendation__action_type=Recommendation.ActionType.SUSTAINABILITY,
    )

    total_count = recommendations.count()

    if total_count == 0:
        return FIFTY

    completed_count = recommendations.filter(
        status=UserRecommendation.Status.COMPLETED
    ).count()

    score = (
        Decimal(completed_count)
        / Decimal(total_count)
        * HUNDRED
    )

    return _round_score(score)


def _calculate_engagement_progress(user) -> Decimal:
    """
    Measure consistency of sustainability tracking across the
    most recent three completed calendar months.

    One tracked month:
        33.33

    Two tracked months:
        66.67

    Three tracked months:
        100

    No completed footprint data:
        50

    This deliberately measures meaningful CarbonIQ tracking behaviour,
    not logins, page views, or arbitrary application usage.
    """

    monthly_emissions = list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )

    if not monthly_emissions:
        return FIFTY

    ordered = sorted(
        monthly_emissions,
        key=lambda row: row["month"],
    )

    recent_months = ordered[-3:]

    tracked_month_count = len(
        {
            row["month"]
            for row in recent_months
        }
    )

    score = (
        Decimal(tracked_month_count)
        / Decimal("3")
        * HUNDRED
    )

    return _round_score(score)


def calculate_eco_score(user) -> EcoScore:
    """
    Calculate the complete deterministic Eco Score for one user.

    The calculation consumes existing CarbonIQ services/data and does
    not create or modify CarbonIQ production records.
    """

    emission_performance = _calculate_emission_performance(user)
    improvement_trend = _calculate_improvement_trend(user)
    sustainable_behaviour = _calculate_sustainable_behaviour(user)
    engagement_progress = _calculate_engagement_progress(user)

    overall_score = (
        emission_performance
        * EMISSION_PERFORMANCE_WEIGHT
        + improvement_trend
        * IMPROVEMENT_TREND_WEIGHT
        + sustainable_behaviour
        * SUSTAINABLE_BEHAVIOUR_WEIGHT
        + engagement_progress
        * ENGAGEMENT_PROGRESS_WEIGHT
    )

    overall_score = _round_score(overall_score)

    return EcoScore(
        overall_score=overall_score,
        emission_performance=emission_performance,
        improvement_trend=improvement_trend,
        sustainable_behaviour=sustainable_behaviour,
        engagement_progress=engagement_progress,
    )