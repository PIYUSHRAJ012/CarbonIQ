from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from typing import Any

import pandas as pd

from ml.services.feature_engineering import (
    MLDataError,
    get_completed_activities,
    normalize_feature_name,
)
from ml.services.model_persistence import (
    ModelPersistenceError,
    load_random_forest_metadata,
    load_random_forest_model,
)


class PredictionServiceError(Exception):
    """
    Raised when a Random Forest prediction cannot be generated safely.
    """


@dataclass(frozen=True)
class CarbonPrediction:
    """
    Result of a CarbonIQ next-month carbon-footprint prediction.
    """

    predicted_emission: float
    feature_period: date
    target_period: date
    model_version: str | None


def _next_month(period: date) -> date:
    """
    Return the first day of the calendar month following `period`.
    """

    if period.month == 12:
        return date(period.year + 1, 1, 1)

    return date(period.year, period.month + 1, 1)


def _build_latest_month_features(user_id: int) -> tuple[pd.DataFrame, date]:
    """
    Build the feature row required by the temporal Random Forest
    from the user's latest completed calendar month.
    """

    activities = [
        activity
        for activity in get_completed_activities()
        if activity.user_id == user_id
    ]

    if not activities:
        raise PredictionServiceError(
            "The user has no completed CarbonIQ activity records "
            "available for prediction."
        )

    active_categories = list(
        {
            activity_entry.category
            for activity in activities
            for activity_entry in activity.entries.all()
            if activity_entry.category.is_active
        }
    )

    if not active_categories:
        raise PredictionServiceError(
            "No active activity categories are available "
            "for prediction."
        )

    feature_name_map: dict[int, str] = {}

    for category in active_categories:
        feature_name = normalize_feature_name(category.name)

        if feature_name in feature_name_map.values():
            raise PredictionServiceError(
                "Activity categories produce duplicate ML feature names."
            )

        feature_name_map[category.id] = feature_name

    canonical_feature_names = sorted(
        feature_name_map.values()
    )

    latest_activity_period = max(
        activity.created_at.date().replace(day=1)
        for activity in activities
    )

    latest_month_activities = [
        activity
        for activity in activities
        if activity.created_at.date().replace(day=1)
        == latest_activity_period
    ]

    feature_values = {
        f"previous_{feature_name}": 0.0
        for feature_name in canonical_feature_names
    }

    total_emission = 0.0

    for activity in latest_month_activities:
        total_emission += float(
            activity.carbon_footprint.total_emission
        )

        for entry in activity.entries.all():
            feature_name = feature_name_map.get(entry.category_id)

            if feature_name is None:
                continue

            feature_values[
                f"previous_{feature_name}"
            ] += float(entry.quantity)

    feature_values["previous_total_emission"] = total_emission
    feature_values["previous_submission_count"] = len(
        latest_month_activities
    )

    return (
        pd.DataFrame([feature_values]),
        latest_activity_period,
    )


def predict_next_month_carbon(user_id: int) -> CarbonPrediction:
    """
    Predict the user's carbon footprint for the month immediately
    following their latest completed activity month.

    The function safely fails when a valid trained Random Forest
    artifact is unavailable.
    """

    try:
        model = load_random_forest_model()
        metadata = load_random_forest_metadata()

    except ModelPersistenceError as exc:
        raise PredictionServiceError(
            f"Random Forest prediction is unavailable: {exc}"
        ) from exc

    prediction_type = metadata.get("prediction_type")

    if prediction_type != "next_month_carbon_footprint":
        raise PredictionServiceError(
            "Persisted Random Forest artifact is not configured "
            "for next-month carbon-footprint prediction."
        )

    feature_names = metadata.get("feature_names")

    if not isinstance(feature_names, list) or not feature_names:
        raise PredictionServiceError(
            "Random Forest metadata does not contain a valid "
            "feature schema."
        )

    X, feature_period = _build_latest_month_features(user_id)

    missing_features = [
        feature_name
        for feature_name in feature_names
        if feature_name not in X.columns
    ]

    if missing_features:
        raise PredictionServiceError(
            "Prediction feature schema is incompatible with the "
            f"persisted model. Missing: {missing_features}"
        )

    unexpected_features = [
        column
        for column in X.columns
        if column not in feature_names
    ]

    if unexpected_features:
        X = X.drop(
            columns=unexpected_features
        )

    X = X.loc[
        :,
        feature_names,
    ]

    if len(feature_names) != getattr(
        model,
        "n_features_in_",
        len(feature_names),
    ):
        raise PredictionServiceError(
            "Persisted Random Forest feature count does not match "
            "its metadata."
        )

    try:
        prediction = model.predict(X)

    except Exception as exc:
        raise PredictionServiceError(
            "Failed to generate Random Forest carbon prediction."
        ) from exc

    if len(prediction) != 1:
        raise PredictionServiceError(
            "Random Forest prediction did not return exactly one value."
        )

    predicted_emission = float(prediction[0])

    if predicted_emission < 0:
        raise PredictionServiceError(
            "Random Forest produced a negative carbon-footprint "
            "prediction."
        )

    target_period = _next_month(feature_period)

    model_version = metadata.get(
        "model_version"
    )

    if model_version is not None:
        model_version = str(model_version)

    return CarbonPrediction(
        predicted_emission=predicted_emission,
        feature_period=feature_period,
        target_period=target_period,
        model_version=model_version,
    )