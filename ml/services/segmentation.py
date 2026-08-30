from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from carbon.models import ActivityCategory
from ml.services.feature_engineering import (
    MLDataError,
    get_completed_activities,
    normalize_feature_name,
)
from ml.services.model_persistence import (
    ModelPersistenceError,
    load_kmeans_metadata,
    load_kmeans_model,
)


class SegmentationPredictionError(Exception):
    """
    Raised when a user's K-Means segment cannot be predicted safely.
    """


@dataclass(frozen=True)
class SegmentationResult:
    """
    Result of a K-Means user-segmentation prediction.
    """

    user_id: int
    cluster_id: int
    model_version: str
    selected_k: int


def get_user_segmentation_features(user_id):
    """
    Build the user-level feature vector required by the K-Means model.

    The returned DataFrame contains exactly one row representing the
    requested user's completed CarbonIQ activity history.

    Args:
        user_id: Primary key of the CarbonIQ user.

    Returns:
        X: pandas.DataFrame
            One-row user feature matrix.

        metadata: pandas.DataFrame
            Metadata containing the user ID.

    Raises:
        MLDataError:
            If the user has no valid completed activity history.
    """

    activities = [
        activity
        for activity in get_completed_activities()
        if activity.user_id == user_id
    ]

    if not activities:
        raise MLDataError(
            "No completed carbon activities with calculated footprints "
            "are available for this user."
        )

    active_categories = (
        ActivityCategory.objects
        .filter(is_active=True)
        .order_by("display_order", "name")
    )

    feature_name_map = {}

    for category in active_categories:
        feature_name = normalize_feature_name(category.name)

        if feature_name in feature_name_map.values():
            raise MLDataError(
                "Activity categories produce duplicate ML feature name: "
                f"'{feature_name}'."
            )

        feature_name_map[category.id] = feature_name

    if not feature_name_map:
        raise MLDataError(
            "No active activity categories are available "
            "for segmentation."
        )

    canonical_feature_names = sorted(
        feature_name_map.values()
    )

    feature_totals = {
        feature_name: 0.0
        for feature_name in canonical_feature_names
    }

    total_emission = 0.0
    submission_count = 0

    for activity in activities:
        for entry in activity.entries.all():
            feature_name = feature_name_map.get(
                entry.category_id
            )

            if feature_name is None:
                continue

            feature_totals[feature_name] += float(
                entry.quantity
            )

        total_emission += float(
            activity.carbon_footprint.total_emission
        )

        submission_count += 1

    if submission_count == 0:
        raise MLDataError(
            "No valid completed submissions are available "
            "for this user."
        )

    row = {
        feature_name: feature_totals[feature_name]
        for feature_name in canonical_feature_names
    }

    row["avg_total_emission"] = (
        total_emission / submission_count
    )

    row["submission_count"] = submission_count

    X = pd.DataFrame(
        [row],
        columns=[
            *canonical_feature_names,
            "avg_total_emission",
            "submission_count",
        ],
    )

    metadata = pd.DataFrame(
        [
            {
                "user_id": user_id,
            }
        ]
    )

    return X, metadata


def predict_user_segment(user_id: int) -> SegmentationResult:
    """
    Predict the K-Means cluster for a CarbonIQ user.

    The user's current segmentation features are generated using the
    same feature-building logic used during model training.

    The persisted StandardScaler and K-Means model are loaded,
    feature-schema compatibility is verified, and the cluster is
    predicted.

    Args:
        user_id: Primary key of the CarbonIQ user.

    Returns:
        SegmentationResult

    Raises:
        MLDataError:
            If the user has no valid completed activity history.

        SegmentationPredictionError:
            If the model cannot be loaded, metadata is invalid, or
            the current feature schema does not match the trained model.
    """

    try:
        X, _metadata = get_user_segmentation_features(
            user_id
        )

    except MLDataError:
        raise

    except Exception as exc:
        raise SegmentationPredictionError(
            f"Failed to build segmentation features for user "
            f"{user_id}: {exc}"
        ) from exc

    try:
        model_bundle = load_kmeans_model()
        model_metadata = load_kmeans_metadata()

    except ModelPersistenceError as exc:
        raise SegmentationPredictionError(
            "Unable to load K-Means segmentation artifacts: "
            f"{exc}"
        ) from exc

    required_metadata_fields = {
        "model_version",
        "features",
        "selected_k",
    }

    missing_fields = (
        required_metadata_fields
        - set(model_metadata.keys())
    )

    if missing_fields:
        raise SegmentationPredictionError(
            "K-Means metadata is missing required fields: "
            f"{sorted(missing_fields)}."
        )

    try:
        expected_features = tuple(
            model_metadata["features"]
        )
    except (TypeError, ValueError) as exc:
        raise SegmentationPredictionError(
            "K-Means metadata contains an invalid feature schema."
        ) from exc

    actual_features = tuple(
        X.columns
    )

    if actual_features != expected_features:
        raise SegmentationPredictionError(
            "K-Means feature schema mismatch. "
            f"Expected {expected_features}, "
            f"but received {actual_features}."
        )

    model = model_bundle["model"]
    scaler = model_bundle["scaler"]

    try:
        X_scaled = scaler.transform(
            X
        )

        predicted_cluster = model.predict(
            X_scaled
        )

    except Exception as exc:
        raise SegmentationPredictionError(
            f"Failed to generate K-Means prediction for user "
            f"{user_id}: {exc}"
        ) from exc

    if len(predicted_cluster) != 1:
        raise SegmentationPredictionError(
            "K-Means prediction did not return exactly one "
            "cluster assignment."
        )

    cluster_id = int(
        predicted_cluster[0]
    )

    return SegmentationResult(
        user_id=int(user_id),
        cluster_id=cluster_id,
        model_version=str(
            model_metadata["model_version"]
        ),
        selected_k=int(
            model_metadata["selected_k"]
        ),
    )