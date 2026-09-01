from dataclasses import dataclass
from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth

from carbon.models import BenchmarkScope, CarbonActivity, CarbonFootprint
from carbon.services.benchmark import BenchmarkResolution, resolve_benchmark


KG_PER_TONNE = Decimal("1000")
MONTHS_PER_YEAR = Decimal("12")


@dataclass(frozen=True)
class MonthlyComparison:
    month: str
    personal_emission_kg: Decimal
    benchmark_emission_kg: Decimal
    difference_kg: Decimal
    difference_percent: Decimal
    below_benchmark: bool


@dataclass(frozen=True)
class BenchmarkComparison:
    benchmark_resolution: BenchmarkResolution
    benchmark_monthly_kg: Decimal
    personal_monthly_comparisons: tuple[MonthlyComparison, ...]


def benchmark_monthly_kg(benchmark_value: Decimal) -> Decimal:
    """
    Convert an annual tCO2/person benchmark into
    kg CO2/person/month.
    """
    return (
        benchmark_value
        * KG_PER_TONNE
        / MONTHS_PER_YEAR
    )


def _calculate_difference_percent(
    personal_emission: Decimal,
    benchmark_emission: Decimal,
) -> Decimal:
    """
    Calculate percentage difference relative to the benchmark.

    Positive result:
        Personal emissions are above the benchmark.

    Negative result:
        Personal emissions are below the benchmark.
    """

    if benchmark_emission == 0:
        return Decimal("0")

    return (
        (personal_emission - benchmark_emission)
        / benchmark_emission
        * Decimal("100")
    )


def get_user_monthly_benchmark_comparison(
    user,
) -> BenchmarkComparison:
    """
    Compare a user's completed monthly carbon footprints
    against the user's resolved benchmark.

    Only COMPLETED activities are included.
    """

    resolution = resolve_benchmark(user)

    benchmark = resolution.benchmark
    monthly_benchmark = benchmark_monthly_kg(benchmark.value)

    monthly_totals = (
        CarbonFootprint.objects.filter(
            carbon_activity__user=user,
            carbon_activity__status=CarbonActivity.Status.COMPLETED,
        )
        .annotate(month=TruncMonth("calculated_at"))
        .values("month")
        .annotate(total=Sum("total_emission"))
        .order_by("month")
    )

    comparisons = []

    for row in monthly_totals:
        personal_emission = row["total"]

        difference = personal_emission - monthly_benchmark

        difference_percent = _calculate_difference_percent(
            personal_emission,
            monthly_benchmark,
        )

        comparisons.append(
            MonthlyComparison(
                month=row["month"].strftime("%Y-%m"),
                personal_emission_kg=personal_emission,
                benchmark_emission_kg=monthly_benchmark,
                difference_kg=difference,
                difference_percent=difference_percent,
                below_benchmark=difference <= 0,
            )
        )

    return BenchmarkComparison(
        benchmark_resolution=resolution,
        benchmark_monthly_kg=monthly_benchmark,
        personal_monthly_comparisons=tuple(comparisons),
    )