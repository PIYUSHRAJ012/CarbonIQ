from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal

from django.db import transaction

from analytics.services.aggregation import AnalyticsAggregationService
from carbon.services.comparison import get_user_monthly_benchmark_comparison
from gamification.models import Achievement, UserAchievement
from recommendations.models import Recommendation, UserRecommendation


MIN_TRACKING_MONTHS = 3
MIN_SUSTAINABILITY_ACTIONS = 3
MIN_EMISSION_REDUCTION_PERCENT = Decimal("10")


DEFAULT_ACHIEVEMENTS = (
    {
        "code": "FIRST_FOOTPRINT",
        "name": "First Footprint",
        "description": (
            "Recorded your first completed carbon footprint."
        ),
        "icon": "fa-leaf",
    },
    {
        "code": "CONSISTENT_TRACKER",
        "name": "Consistent Tracker",
        "description": (
            "Tracked your carbon footprint across at least "
            "three calendar months."
        ),
        "icon": "fa-calendar-check",
    },
    {
        "code": "EMISSION_REDUCER",
        "name": "Emission Reducer",
        "description": (
            "Reduced your monthly carbon footprint by at least "
            "10% compared with the previous month."
        ),
        "icon": "fa-arrow-down",
    },
    {
        "code": "SUSTAINABILITY_ACTION_CHAMPION",
        "name": "Sustainability Action Champion",
        "description": (
            "Completed at least three personalized sustainability "
            "recommendations."
        ),
        "icon": "fa-seedling",
    },
    {
        "code": "LOW_CARBON_MONTH",
        "name": "Low Carbon Month",
        "description": (
            "Recorded a completed month below your resolved "
            "CarbonIQ benchmark."
        ),
        "icon": "fa-earth-asia",
    },
)


@dataclass(frozen=True)
class AchievementEvaluationResult:
    """
    Result returned after evaluating one user's achievements.
    """

    earned: tuple[Achievement, ...]
    newly_awarded: tuple[Achievement, ...]


def seed_default_achievements() -> tuple[Achievement, ...]:
    """
    Ensure that the default CarbonIQ achievement catalog exists.

    The operation is idempotent and does not modify existing
    achievement definitions.
    """

    achievements = []

    for definition in DEFAULT_ACHIEVEMENTS:
        achievement, _ = Achievement.objects.get_or_create(
            code=definition["code"],
            defaults={
                "name": definition["name"],
                "description": definition["description"],
                "icon": definition["icon"],
                "is_active": True,
            },
        )

        achievements.append(achievement)

    return tuple(achievements)


def _completed_footprint_count(user) -> int:
    """
    Return the number of completed calendar months containing
    footprint data.
    """

    monthly_emissions = list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )

    return len(monthly_emissions)


def _tracked_month_count(user) -> int:
    """
    Return the number of distinct calendar months in which the user
    has completed footprint data.
    """

    monthly_emissions = list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )

    return len(
        {
            row["month"]
            for row in monthly_emissions
        }
    )


def _has_emission_reduction(user) -> bool:
    """
    Return True when the latest completed month is at least 10%
    lower than the immediately preceding completed month.
    """

    monthly_emissions = list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )

    if len(monthly_emissions) < 2:
        return False

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

    if previous <= Decimal("0"):
        return False

    reduction_percent = (
        (previous - latest)
        / previous
        * Decimal("100")
    )

    return reduction_percent >= MIN_EMISSION_REDUCTION_PERCENT


def _completed_sustainability_action_count(user) -> int:
    """
    Count completed sustainability recommendations.

    Offset recommendations are deliberately excluded.
    """

    return (
        UserRecommendation.objects
        .filter(
            user=user,
            recommendation__action_type=(
                Recommendation.ActionType.SUSTAINABILITY
            ),
            status=UserRecommendation.Status.COMPLETED,
        )
        .count()
    )


def _has_low_carbon_month(user) -> bool:
    """
    Return True when at least one completed month is at or below
    the user's resolved E4 benchmark.
    """

    try:
        comparison = get_user_monthly_benchmark_comparison(user)
    except Exception:
        return False

    return any(
        row.below_benchmark
        for row in comparison.personal_monthly_comparisons
    )


def _is_eligible(
    *,
    code: str,
    user,
) -> bool:
    """
    Evaluate the eligibility rule associated with one achievement.
    """

    if code == "FIRST_FOOTPRINT":
        return _completed_footprint_count(user) >= 1

    if code == "CONSISTENT_TRACKER":
        return _tracked_month_count(user) >= MIN_TRACKING_MONTHS

    if code == "EMISSION_REDUCER":
        return _has_emission_reduction(user)

    if code == "SUSTAINABILITY_ACTION_CHAMPION":
        return (
            _completed_sustainability_action_count(user)
            >= MIN_SUSTAINABILITY_ACTIONS
        )

    if code == "LOW_CARBON_MONTH":
        return _has_low_carbon_month(user)

    return False


@transaction.atomic
def evaluate_achievements(
    user,
) -> AchievementEvaluationResult:
    """
    Evaluate all active achievements for one user.

    Already-earned achievements remain unchanged.

    The method is safe to call repeatedly:
    no duplicate UserAchievement records are created.
    """

    achievements = seed_default_achievements()

    existing_codes = set(
        UserAchievement.objects
        .filter(
            user=user,
            achievement__in=achievements,
        )
        .values_list(
            "achievement__code",
            flat=True,
        )
    )

    earned = []
    newly_awarded = []

    for achievement in achievements:
        if not achievement.is_active:
            continue

        if not _is_eligible(
            code=achievement.code,
            user=user,
        ):
            continue

        earned.append(achievement)

        if achievement.code in existing_codes:
            continue

        UserAchievement.objects.get_or_create(
            user=user,
            achievement=achievement,
        )

        newly_awarded.append(achievement)

    return AchievementEvaluationResult(
        earned=tuple(earned),
        newly_awarded=tuple(newly_awarded),
    )