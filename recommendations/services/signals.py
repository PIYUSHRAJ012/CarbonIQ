from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from analytics.services.aggregation import AnalyticsAggregationService

from ml.services.segmentation import SegmentationPredictionError
from ml.services.segmentation_profile import (
    UserSegmentProfileError,
    get_user_segment_profile,
)


@dataclass(frozen=True)
class RecommendationSignals:
    """
    Consolidated CarbonIQ signals used by the recommendation engine.

    This object intentionally contains only application-facing signals.
    Carbon calculations and ML internals remain owned by their
    respective services.
    """

    total_emission: Decimal

    category_emissions: tuple[dict[str, Any], ...]
    monthly_emissions: tuple[dict[str, Any], ...]
    weekly_emissions: tuple[dict[str, Any], ...]

    top_category: str | None
    top_category_emission: Decimal

    rf_prediction: float | None = None

    user_segment: str | None = None
    dominant_domain: str | None = None
    segment_domain_scores: dict[str, float] | None = None
    segment_feature_strengths: dict[str, float] | None = None
    segment_model_version: str | None = None
    segment_selected_k: int | None = None


class RecommendationSignalError(Exception):
    """
    Raised when recommendation signals cannot be assembled safely.
    """


def _to_decimal(value: Any) -> Decimal:
    """
    Convert numeric values into Decimal for consistent scoring input.
    """

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except Exception as exc:
        raise RecommendationSignalError(
            f"Unable to convert value '{value}' to Decimal."
        ) from exc


def build_recommendation_signals(user) -> RecommendationSignals:
    """
    Build the consolidated recommendation signal set for one user.

    Analytics signals are mandatory.

    ML signals are optional. If a trained K-Means model is unavailable,
    or segmentation inference cannot be performed yet, recommendation
    generation continues using the available CarbonIQ and analytics data.

    Random Forest remains optional until its verified application-facing
    prediction interface is connected.
    """

    # -------------------------------------------------------------
    # Analytics signals
    # -------------------------------------------------------------
    try:
        total_emission = (
            AnalyticsAggregationService.get_total_emission(user)
        )

        category_rows = tuple(
            AnalyticsAggregationService.get_category_emissions(user)
        )

        monthly_rows = tuple(
            AnalyticsAggregationService.get_monthly_emissions(user)
        )

        weekly_rows = tuple(
            AnalyticsAggregationService.get_weekly_emissions(user)
        )

    except Exception as exc:
        raise RecommendationSignalError(
            "Failed to build analytics signals for the user."
        ) from exc

    # -------------------------------------------------------------
    # Top category
    # -------------------------------------------------------------
    top_category = None
    top_category_emission = Decimal("0.0000")

    if category_rows:
        top_category = category_rows[0].get(
            "category__name"
        )

        top_category_emission = _to_decimal(
            category_rows[0].get(
                "total_emission",
                Decimal("0.0000"),
            )
        )

    # -------------------------------------------------------------
    # K-Means user segmentation
    # -------------------------------------------------------------
    user_segment = None
    dominant_domain = None
    segment_domain_scores = None
    segment_feature_strengths = None
    segment_model_version = None
    segment_selected_k = None

    try:
        segment_profile = get_user_segment_profile(
            user.id
        )

        user_segment = segment_profile.profile_name
        dominant_domain = segment_profile.dominant_domain

        segment_domain_scores = {
            str(key): float(value)
            for key, value in segment_profile.domain_scores.items()
        }

        segment_feature_strengths = {
            str(key): float(value)
            for key, value in segment_profile.feature_strengths.items()
        }

        segment_model_version = segment_profile.model_version
        segment_selected_k = segment_profile.selected_k

    except (
        UserSegmentProfileError,
        SegmentationPredictionError,
    ):
        # K-Means is optional.
        #
        # This covers cases such as:
        # - model artifact not available
        # - metadata unavailable
        # - insufficient production data
        # - segmentation inference failure
        #
        # Recommendation generation must continue using the
        # available carbon and analytics signals.
        pass

    # -------------------------------------------------------------
    # Consolidated signal object
    # -------------------------------------------------------------
    return RecommendationSignals(
        total_emission=_to_decimal(
            total_emission
        ),
        category_emissions=category_rows,
        monthly_emissions=monthly_rows,
        weekly_emissions=weekly_rows,
        top_category=top_category,
        top_category_emission=top_category_emission,
        rf_prediction=None,
        user_segment=user_segment,
        dominant_domain=dominant_domain,
        segment_domain_scores=segment_domain_scores,
        segment_feature_strengths=segment_feature_strengths,
        segment_model_version=segment_model_version,
        segment_selected_k=segment_selected_k,
    )