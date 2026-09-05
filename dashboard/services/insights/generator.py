from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from .contracts import Insight, InsightType
from .signals import InsightSignals


# Deterministic priorities used by the later E7 ranker.
ACTION_PRIORITY = 100
EMISSION_DRIVER_PRIORITY = 90
PREDICTION_PRIORITY = 80
BENCHMARK_PRIORITY = 70
TREND_PRIORITY = 60
SEGMENT_PRIORITY = 50
ENVIRONMENTAL_CONTEXT_PRIORITY = 40

_PERCENT = Decimal("100")
_SIGNIFICANT_TREND_CHANGE = Decimal("20")


def _as_decimal(value: Any) -> Decimal | None:
    """
    Safely normalize numeric values to Decimal.
    """
    if value is None:
        return None

    if isinstance(value, Decimal):
        return value

    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _format_decimal(
    value: Decimal,
    places: int = 2,
) -> str:
    """
    Format Decimal values consistently for user-facing messages.
    """
    return f"{value:.{places}f}"


def _build_trend_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Generate a trend insight from the two most recent months.
    """

    if len(signals.monthly_emissions) < 2:
        return None

    previous = _as_decimal(
        signals.monthly_emissions[-2]["total_emission"]
    )
    latest = _as_decimal(
        signals.monthly_emissions[-1]["total_emission"]
    )

    if previous is None or latest is None:
        return None

    if latest > previous:
        change_percent = (
            ((latest - previous) / previous) * _PERCENT
            if previous > 0
            else None
        )

        priority = TREND_PRIORITY

        if (
            change_percent is not None
            and change_percent >= _SIGNIFICANT_TREND_CHANGE
        ):
            priority += 10

        return Insight(
            type=InsightType.TREND,
            title="Your carbon footprint is increasing",
            message=(
                f"Your emissions increased from "
                f"{_format_decimal(previous)} kg CO2e to "
                f"{_format_decimal(latest)} kg CO2e between your two "
                f"most recent recorded months."
            ),
            priority=priority,
            source="analytics",
            metric=latest,
            metric_unit="kg CO2e",
        )

    if latest < previous:
        return Insight(
            type=InsightType.TREND,
            title="Your carbon footprint is decreasing",
            message=(
                f"Your emissions decreased from "
                f"{_format_decimal(previous)} kg CO2e to "
                f"{_format_decimal(latest)} kg CO2e between your two "
                f"most recent recorded months."
            ),
            priority=TREND_PRIORITY - 5,
            source="analytics",
            metric=latest,
            metric_unit="kg CO2e",
        )

    return Insight(
        type=InsightType.TREND,
        title="Your carbon footprint is stable",
        message=(
            f"Your two most recent recorded months both show "
            f"{_format_decimal(latest)} kg CO2e."
        ),
        priority=TREND_PRIORITY - 10,
        source="analytics",
        metric=latest,
        metric_unit="kg CO2e",
    )


def _build_emission_driver_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Explain the user's largest recorded emission category.
    """

    if (
        not signals.top_category
        or signals.top_category_emission is None
    ):
        return None

    total = _as_decimal(signals.current_total_emission)
    category_emission = _as_decimal(
        signals.top_category_emission
    )

    if (
        total is None
        or category_emission is None
        or total <= 0
    ):
        return None

    share = (category_emission / total) * _PERCENT

    return Insight(
        type=InsightType.EMISSION_DRIVER,
        title=(
            f"Your largest emission driver is "
            f"{signals.top_category}"
        ),
        message=(
            f"{signals.top_category} contributes approximately "
            f"{_format_decimal(share, 1)}% of your recorded carbon "
            f"footprint ({_format_decimal(category_emission)} kg CO2e). "
            f"Focusing on this area is a strong evidence-based "
            f"starting point for reducing your footprint."
        ),
        priority=EMISSION_DRIVER_PRIORITY,
        source="analytics",
        metric=category_emission,
        metric_unit="kg CO2e",
    )


def _build_prediction_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Generate an interpretation of an available Random Forest prediction.

    No prediction means no prediction insight.
    """

    prediction = signals.prediction

    if prediction is None:
        return None

    predicted_emission = _as_decimal(
        getattr(prediction, "predicted_emission", None)
    )
    target_period = getattr(
        prediction,
        "target_period",
        None,
    )
    model_version = getattr(
        prediction,
        "model_version",
        None,
    )

    if predicted_emission is None or target_period is None:
        return None

    period_label = target_period.strftime("%B %Y")

    model_suffix = (
        f" Model version: {model_version}."
        if model_version
        else ""
    )

    return Insight(
        type=InsightType.PREDICTION,
        title="Next-month carbon outlook",
        message=(
            f"The current Random Forest model estimates approximately "
            f"{_format_decimal(predicted_emission)} kg CO2e "
            f"for {period_label}.{model_suffix}"
        ),
        priority=PREDICTION_PRIORITY,
        source="ml.random_forest",
        metric=predicted_emission,
        metric_unit="kg CO2e",
    )


def _build_segment_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Generate an interpretation of an available K-Means segment profile.
    """

    segment = signals.user_segment

    if segment is None:
        return None

    profile_name = getattr(
        segment,
        "profile_name",
        None,
    )
    dominant_domain = getattr(
        segment,
        "dominant_domain",
        None,
    )
    cluster_id = getattr(
        segment,
        "cluster_id",
        None,
    )

    if not profile_name:
        return None

    detail = (
        f", with {dominant_domain} identified as your dominant area"
        if dominant_domain
        else ""
    )

    cluster_detail = (
        f" (segment {cluster_id})"
        if cluster_id is not None
        else ""
    )

    return Insight(
        type=InsightType.SEGMENT,
        title="Your sustainability profile",
        message=(
            f"Your current sustainability profile is "
            f"{profile_name}{detail}{cluster_detail}."
        ),
        priority=SEGMENT_PRIORITY,
        source="ml.kmeans",
        metric=None,
        metric_unit=None,
    )


def _build_benchmark_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Generate an insight from the latest available E4 benchmark comparison.
    """

    benchmark = signals.benchmark

    if benchmark is None:
        return None

    comparisons = getattr(
        benchmark,
        "personal_monthly_comparisons",
        (),
    )

    if not comparisons:
        return None

    comparison = comparisons[-1]

    personal = _as_decimal(
        getattr(
            comparison,
            "personal_emission_kg",
            None,
        )
    )
    benchmark_value = _as_decimal(
        getattr(
            comparison,
            "benchmark_emission_kg",
            None,
        )
    )
    difference = _as_decimal(
        getattr(
            comparison,
            "difference_kg",
            None,
        )
    )
    difference_percent = _as_decimal(
        getattr(
            comparison,
            "difference_percent",
            None,
        )
    )
    below_benchmark = getattr(
        comparison,
        "below_benchmark",
        None,
    )
    month = getattr(
        comparison,
        "month",
        None,
    )

    if (
        personal is None
        or benchmark_value is None
        or difference is None
        or difference_percent is None
        or below_benchmark is None
    ):
        return None

    if below_benchmark:
        title = "You are below your benchmark"

        message = (
            f"For {month}, your footprint was "
            f"{_format_decimal(personal)} kg CO2e, which is "
            f"{_format_decimal(abs(difference))} kg CO2e "
            f"({_format_decimal(abs(difference_percent), 1)}%) "
            f"below the benchmark of "
            f"{_format_decimal(benchmark_value)} kg CO2e."
        )

    else:
        title = "Your footprint is above your benchmark"

        message = (
            f"For {month}, your footprint was "
            f"{_format_decimal(personal)} kg CO2e, which is "
            f"{_format_decimal(difference)} kg CO2e "
            f"({_format_decimal(difference_percent, 1)}%) "
            f"above the benchmark of "
            f"{_format_decimal(benchmark_value)} kg CO2e."
        )

    return Insight(
        type=InsightType.BENCHMARK,
        title=title,
        message=message,
        priority=BENCHMARK_PRIORITY,
        source="benchmarking",
        metric=difference,
        metric_unit="kg CO2e",
    )


def _build_environmental_context_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Generate contextual insight from persisted E6 environmental data.

    This does not call the external provider.
    """

    environment = signals.external_environment

    if environment is None:
        return None

    value = _as_decimal(
        getattr(environment, "value", None)
    )
    zone = getattr(
        environment,
        "zone",
        None,
    )
    unit = getattr(
        environment,
        "unit",
        None,
    )
    provider = getattr(
        environment,
        "provider",
        None,
    )
    is_estimated = getattr(
        environment,
        "is_estimated",
        False,
    )

    if value is None or not zone or not unit:
        return None

    if is_estimated:
        estimation_method = getattr(
            environment,
            "estimation_method",
            "",
        )

        provenance = (
            "This observation is estimated"
            f" via {estimation_method}."
            if estimation_method
            else "This observation is estimated."
        )
    else:
        provenance = f"Source: {provider}."

    return Insight(
        type=InsightType.ENVIRONMENTAL_CONTEXT,
        title="Current grid carbon context",
        message=(
            f"The latest available grid carbon intensity for "
            f"{zone} is {_format_decimal(value)} {unit}. "
            f"{provenance}"
        ),
        priority=ENVIRONMENTAL_CONTEXT_PRIORITY,
        source="external_data",
        metric=value,
        metric_unit=unit,
    )


def _build_action_priority_insight(
    signals: InsightSignals,
) -> Insight | None:
    """
    Identify the strongest currently available sustainability action signal.

    This is deterministic prioritization, not another ML model.
    """

    if signals.recommendations:
        recommendation = signals.recommendations[0]

        catalog = getattr(
            recommendation,
            "recommendation",
            None,
        )

        title = getattr(
            catalog,
            "title",
            None,
        )

        if title:
            reason = getattr(
                recommendation,
                "reason",
                None,
            )

            message = (
                f"Your current personalized action priority is: "
                f"{title}."
            )

            if reason:
                message += f" Reason: {reason}"

            return Insight(
                type=InsightType.ACTION_PRIORITY,
                title="Highest-priority sustainability action",
                message=message,
                priority=ACTION_PRIORITY,
                source="recommendations+analytics",
                metric=None,
                metric_unit=None,
            )

    if signals.top_category:
        return Insight(
            type=InsightType.ACTION_PRIORITY,
            title="Highest-impact area to focus on",
            message=(
                f"Your largest recorded emission driver is "
                f"{signals.top_category}. Focusing on this area "
                f"is the strongest evidence-based starting point "
                f"in your current footprint data."
            ),
            priority=ACTION_PRIORITY,
            source="analytics",
            metric=signals.top_category_emission,
            metric_unit="kg CO2e",
        )

    return None


def _deduplicate_insights(
    insights: list[Insight],
) -> tuple[Insight, ...]:
    """
    Remove exact duplicate insights while preserving order.
    """

    seen: set[tuple[InsightType, str, str]] = set()
    unique: list[Insight] = []

    for insight in insights:
        key = (
            insight.type,
            insight.title,
            insight.message,
        )

        if key in seen:
            continue

        seen.add(key)
        unique.append(insight)

    return tuple(unique)


def generate_insights(
    signals: InsightSignals,
) -> tuple[Insight, ...]:
    """
    Convert assembled E7 signals into deterministic user-facing insights.

    This layer interprets existing signals. It does not:
    - calculate carbon emissions
    - train ML models
    - call external APIs
    - generate recommendations
    - create database records
    """

    insights = [
        insight
        for insight in (
            _build_trend_insight(signals),
            _build_emission_driver_insight(signals),
            _build_prediction_insight(signals),
            _build_segment_insight(signals),
            _build_benchmark_insight(signals),
            _build_environmental_context_insight(signals),
            _build_action_priority_insight(signals),
        )
        if insight is not None
    ]

    return _deduplicate_insights(insights)