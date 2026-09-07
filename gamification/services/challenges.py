from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal

from django.db import transaction
from django.utils import timezone

from analytics.services.aggregation import AnalyticsAggregationService
from carbon.services.comparison import get_user_monthly_benchmark_comparison

from gamification.models import Challenge, UserChallenge
from recommendations.models import Recommendation, UserRecommendation


ZERO = Decimal("0")
HUNDRED = Decimal("100")


@dataclass(frozen=True)
class ChallengeProgress:
    """
    Server-calculated challenge progress.

    raw_progress:
        Actual measured progress from CarbonIQ data.

    progress:
        Raw progress capped at the challenge target.

    completed:
        Whether the target has been reached.
    """

    raw_progress: Decimal
    progress: Decimal
    completed: bool


def _today() -> date:
    """
    Return the current application-local date.
    """

    return timezone.localdate()


def is_challenge_available(
    challenge: Challenge,
    *,
    today: date | None = None,
) -> bool:
    """
    Return whether a challenge can currently be joined.

    Requirements:
    - challenge must be active
    - current date must be on/after start_date
    - current date must be on/before end_date
    """

    if today is None:
        today = _today()

    return (
        challenge.is_active
        and challenge.start_date <= today <= challenge.end_date
    )


def get_active_challenges(
    *,
    today: date | None = None,
):
    """
    Return challenges currently available for participation.
    """

    if today is None:
        today = _today()

    return (
        Challenge.objects
        .filter(
            is_active=True,
            start_date__lte=today,
            end_date__gte=today,
        )
        .order_by("end_date", "title")
    )


def _get_monthly_emissions(user):
    """
    Return completed monthly emissions as a list ordered by month.
    """

    return list(
        AnalyticsAggregationService.get_monthly_emissions(user)
    )


def _calculate_emission_reduction(user) -> Decimal:
    """
    Return the percentage reduction from the previous completed
    month to the latest completed month.

    Example:
        previous = 100
        latest = 80

        reduction = 20%
    """

    monthly_emissions = _get_monthly_emissions(user)

    if len(monthly_emissions) < 2:
        return ZERO

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
        return ZERO

    reduction = (
        (previous - latest)
        / previous
        * HUNDRED
    )

    return max(ZERO, reduction)


def _calculate_sustainable_actions(user) -> Decimal:
    """
    Return the number of completed sustainability recommendations.

    Offset recommendations are intentionally excluded.
    """

    count = (
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

    return Decimal(count)


def _calculate_monthly_improvements(user) -> Decimal:
    """
    Count completed month-to-month transitions where emissions
    decreased relative to the immediately preceding completed month.

    Example:

        Jan = 100
        Feb = 90   -> improvement
        Mar = 95   -> no improvement
        Apr = 80   -> improvement

    Result = 2
    """

    monthly_emissions = _get_monthly_emissions(user)

    if len(monthly_emissions) < 2:
        return ZERO

    ordered = sorted(
        monthly_emissions,
        key=lambda row: row["month"],
    )

    improvements = 0

    for previous, latest in zip(
        ordered,
        ordered[1:],
    ):
        previous_value = Decimal(
            str(previous["total_emission"])
        )

        latest_value = Decimal(
            str(latest["total_emission"])
        )

        if latest_value < previous_value:
            improvements += 1

    return Decimal(improvements)


def _calculate_low_emission_periods(user) -> Decimal:
    """
    Count completed calendar months at or below the user's
    resolved E4 monthly benchmark.
    """

    try:
        comparison = (
            get_user_monthly_benchmark_comparison(user)
        )
    except Exception:
        return ZERO

    count = sum(
        1
        for row in comparison.personal_monthly_comparisons
        if row.below_benchmark
    )

    return Decimal(count)


def calculate_challenge_progress(
    challenge: Challenge,
    user,
) -> ChallengeProgress:
    """
    Calculate server-validated progress for a challenge.
    """

    if challenge.metric == Challenge.Metric.EMISSION_REDUCTION:
        raw_progress = _calculate_emission_reduction(user)

    elif challenge.metric == Challenge.Metric.SUSTAINABLE_ACTIONS:
        raw_progress = _calculate_sustainable_actions(user)

    elif challenge.metric == Challenge.Metric.MONTHLY_IMPROVEMENT:
        raw_progress = _calculate_monthly_improvements(user)

    elif challenge.metric == Challenge.Metric.LOW_EMISSION_PERIOD:
        raw_progress = _calculate_low_emission_periods(user)

    else:
        raw_progress = ZERO

    target = max(
        ZERO,
        Decimal(str(challenge.target)),
    )

    if target == ZERO:
        completed = raw_progress >= ZERO
        capped_progress = ZERO
    else:
        completed = raw_progress >= target
        capped_progress = min(
            raw_progress,
            target,
        )

    return ChallengeProgress(
        raw_progress=raw_progress,
        progress=capped_progress,
        completed=completed,
    )


def join_challenge(
    user,
    challenge: Challenge,
    *,
    today: date | None = None,
) -> UserChallenge:
    """
    Enrol a user into an active challenge.

    Existing participation is returned unchanged.

    A challenge outside its active date window cannot be joined.
    """

    if today is None:
        today = _today()

    if not is_challenge_available(
        challenge,
        today=today,
    ):
        raise ValueError(
            "Challenge is not currently available."
        )

    user_challenge, _ = UserChallenge.objects.get_or_create(
        user=user,
        challenge=challenge,
    )

    return user_challenge


@transaction.atomic
def update_challenge_progress(
    user_challenge: UserChallenge,
) -> ChallengeProgress:
    """
    Recalculate and persist validated challenge progress.

    The browser never supplies the progress value.
    """

    challenge = user_challenge.challenge

    challenge_progress = calculate_challenge_progress(
        challenge,
        user_challenge.user,
    )

    update_fields = [
        "progress",
        "completed",
    ]

    user_challenge.progress = challenge_progress.progress
    user_challenge.completed = challenge_progress.completed

    if (
        challenge_progress.completed
        and user_challenge.completed_at is None
    ):
        user_challenge.completed_at = timezone.now()
        update_fields.append("completed_at")

    user_challenge.save(
        update_fields=update_fields
    )

    return challenge_progress