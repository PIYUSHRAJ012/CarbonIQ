from dataclasses import dataclass

from carbon.models import BenchmarkScope, CarbonBenchmark, UserLocation


@dataclass(frozen=True)
class BenchmarkResolution:
    """
    Result of resolving the most appropriate benchmark for a user.

    benchmark:
        The CarbonBenchmark selected for comparison.

    scope:
        The scope actually used (DISTRICT or NATIONAL).

    used_fallback:
        True when the district benchmark was unavailable and the
        national benchmark was used instead.

    reason:
        Human-readable explanation of why this benchmark was selected.
    """

    benchmark: CarbonBenchmark
    scope: str
    used_fallback: bool
    reason: str


def _normalize_location_name(value: str) -> str:
    """
    Normalize a location name for comparison.

    This does not modify database values. It only makes matching
    tolerant of capitalization and repeated whitespace.
    """
    return " ".join(value.strip().split()).casefold()


def _find_district_benchmark(
    state: str,
    district: str,
) -> CarbonBenchmark | None:
    """
    Find an active district benchmark matching the user's location.
    """

    normalized_state = _normalize_location_name(state)
    normalized_district = _normalize_location_name(district)

    candidates = CarbonBenchmark.objects.filter(
        scope=BenchmarkScope.DISTRICT,
        is_active=True,
        state__iexact=state.strip(),
    ).order_by("district", "-updated_at")

    for benchmark in candidates:
        if (
            _normalize_location_name(benchmark.state) == normalized_state
            and _normalize_location_name(benchmark.district)
            == normalized_district
        ):
            return benchmark

    return None


def _find_national_benchmark() -> CarbonBenchmark | None:
    """
    Return the active India national benchmark.

    If multiple active national versions exist in the future,
    the most recently updated one is selected deterministically.
    """

    return (
        CarbonBenchmark.objects.filter(
            scope=BenchmarkScope.NATIONAL,
            is_active=True,
        )
        .order_by("-updated_at")
        .first()
    )


def resolve_benchmark(user) -> BenchmarkResolution:
    """
    Resolve the best available benchmark for a CarbonIQ user.

    Resolution hierarchy:

        1. User's district benchmark
        2. India national benchmark

    Raises:
        ValueError:
            If the user has no location or if no active national
            benchmark is available.
    """

    try:
        location = user.location
    except UserLocation.DoesNotExist:
        raise ValueError(
            "User location is not configured. "
            "Please provide state and district before benchmarking."
        )

    district_benchmark = _find_district_benchmark(
        state=location.state,
        district=location.district,
    )

    if district_benchmark is not None:
        return BenchmarkResolution(
            benchmark=district_benchmark,
            scope=BenchmarkScope.DISTRICT,
            used_fallback=False,
            reason=(
                f"District benchmark found for "
                f"{location.district}, {location.state}."
            ),
        )

    national_benchmark = _find_national_benchmark()

    if national_benchmark is None:
        raise ValueError(
            "No active national carbon benchmark is available."
        )

    return BenchmarkResolution(
        benchmark=national_benchmark,
        scope=BenchmarkScope.NATIONAL,
        used_fallback=True,
        reason=(
            f"No district benchmark was found for "
            f"{location.district}, {location.state}; "
            "using the India national benchmark."
        ),
    )