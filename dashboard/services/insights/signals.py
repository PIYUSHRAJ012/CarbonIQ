from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any

from analytics.services.aggregation import AnalyticsAggregationService
from carbon.models import UserLocation
from carbon.services.comparison import get_user_monthly_benchmark_comparison
from external_data.models import ExternalEnvironmentalObservation
from ml.services.prediction import (
    PredictionServiceError,
    predict_next_month_carbon,
)
from ml.services.segmentation import SegmentationPredictionError
from ml.services.segmentation_profile import (
    UserSegmentProfileError,
    get_user_segment_profile,
)
from recommendations.models import OffsetRecommendation, UserRecommendation


@dataclass(frozen=True, slots=True)
class InsightSignals:
    """
    Immutable collection of signals available to the E7 insight layer.

    The object contains already-computed or already-resolved values from
    existing CarbonIQ services. E7 must interpret these signals and must
    not reimplement the underlying business logic.
    """

    # ------------------------------------------------------------------
    # Core carbon / analytics signals
    # ------------------------------------------------------------------

    current_total_emission: Decimal | None = None

    monthly_emissions: tuple[Any, ...] = ()
    weekly_emissions: tuple[Any, ...] = ()
    category_emissions: tuple[Any, ...] = ()

    top_category: str | None = None
    top_category_emission: Decimal | None = None

    # ------------------------------------------------------------------
    # E2 — Machine Learning signals
    # ------------------------------------------------------------------

    prediction: Any | None = None
    user_segment: Any | None = None

    # ------------------------------------------------------------------
    # E3 — Recommendation signals
    # ------------------------------------------------------------------

    recommendations: tuple[Any, ...] = ()

    # ------------------------------------------------------------------
    # E4 — Benchmarking signals
    # ------------------------------------------------------------------

    benchmark: Any | None = None

    # ------------------------------------------------------------------
    # E5 — Carbon offset guidance
    # ------------------------------------------------------------------

    offset_context: Any | None = None

    # ------------------------------------------------------------------
    # E6 — External environmental data
    # ------------------------------------------------------------------

    external_environment: Any | None = None


@dataclass(frozen=True, slots=True)
class ExternalEnvironmentSignal:
    """
    Immutable external environmental context resolved from persisted E6 data.
    """

    provider: str
    zone: str
    value: Decimal
    unit: str
    observed_at: datetime
    fetched_at: datetime
    is_estimated: bool
    estimation_method: str
    temporal_granularity: str
    emission_factor_type: str
    source_url: str


class InsightSignalError(Exception):
    """
    Raised when mandatory insight signals cannot be assembled safely.
    """


def _get_external_environment_signal(user) -> ExternalEnvironmentSignal | None:
    """
    Resolve the latest compatible persisted E6 observation for a user's state.

    This deliberately reads only local observations and never invokes an
    external-data provider.
    """

    location = UserLocation.objects.filter(user=user).only("state").first()
    if location is None:
        return None

    state = location.state.strip()
    if not state:
        return None

    observation = (
        ExternalEnvironmentalObservation.objects.filter(
            data_type=(
                ExternalEnvironmentalObservation.DataType.GRID_CARBON_INTENSITY
            ),
            zone__iexact=state,
            temporal_granularity=(
                ExternalEnvironmentalObservation.TemporalGranularity.HOURLY
            ),
            emission_factor_type=(
                ExternalEnvironmentalObservation.EmissionFactorType.LIFECYCLE
            ),
            flow_traced=False,
        )
        .order_by("-observed_at", "-fetched_at")
        .first()
    )

    if observation is None:
        return None

    return ExternalEnvironmentSignal(
        provider=observation.provider,
        zone=observation.zone,
        value=observation.value,
        unit=observation.unit,
        observed_at=observation.observed_at,
        fetched_at=observation.fetched_at,
        is_estimated=observation.is_estimated,
        estimation_method=observation.estimation_method,
        temporal_granularity=observation.temporal_granularity,
        emission_factor_type=observation.emission_factor_type,
        source_url=observation.source_url,
    )


def build_insight_signals(user) -> InsightSignals:
    """
    Assemble the immutable E7 signal set for one user.

    Analytics is mandatory because it is the foundation of the insight layer.
    Prediction, segmentation, benchmark, recommendations, offsets, and E6
    environmental context are supplementary signals and may be unavailable.
    """

    try:
        monthly_emissions = tuple(
            AnalyticsAggregationService.get_monthly_emissions(user)
        )
        weekly_emissions = tuple(
            AnalyticsAggregationService.get_weekly_emissions(user)
        )
        category_emissions = tuple(
            AnalyticsAggregationService.get_category_emissions(user)
        )
        current_total_emission = AnalyticsAggregationService.get_total_emission(
            user
        )
    except Exception as exc:
        raise InsightSignalError(
            "Failed to build analytics insight signals for the user."
        ) from exc

    top_category = None
    top_category_emission = None
    if category_emissions:
        top_category = category_emissions[0]["category__name"]
        top_category_emission = category_emissions[0]["total_emission"]

    try:
        prediction = predict_next_month_carbon(user.id)
    except PredictionServiceError:
        prediction = None

    try:
        user_segment = get_user_segment_profile(user.id)
    except (UserSegmentProfileError, SegmentationPredictionError):
        user_segment = None

    try:
        benchmark = get_user_monthly_benchmark_comparison(user)
    except ValueError:
        benchmark = None

    recommendations = tuple(
        UserRecommendation.objects.filter(
            user=user,
            status=UserRecommendation.Status.ACTIVE,
        )
        .select_related("recommendation", "recommendation__category")
        .order_by("-score", "-generated_at")
    )

    offset_context = tuple(
        OffsetRecommendation.objects.filter(
            user=user,
            status=OffsetRecommendation.Status.ACTIVE,
        )
        .select_related("offset_project")
        .order_by("-score", "-generated_at")
    )

    external_environment = _get_external_environment_signal(user)

    return InsightSignals(
        current_total_emission=current_total_emission,
        monthly_emissions=monthly_emissions,
        weekly_emissions=weekly_emissions,
        category_emissions=category_emissions,
        top_category=top_category,
        top_category_emission=top_category_emission,
        prediction=prediction,
        user_segment=user_segment,
        recommendations=recommendations,
        benchmark=benchmark,
        offset_context=offset_context,
        external_environment=external_environment,
    )
