from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from ml.services.cluster_interpretation import (
    ClusterInterpretationError,
    interpret_cluster,
)
from ml.services.model_persistence import (
    ModelPersistenceError,
    load_kmeans_metadata,
    load_kmeans_model,
)
from ml.services.segmentation import (
    SegmentationPredictionError,
    predict_user_segment,
)
from ml.services.feature_engineering import MLDataError


class UserSegmentProfileError(Exception):
    """
    Raised when a complete user segment profile cannot be generated.
    """


@dataclass(frozen=True)
class UserSegmentProfile:
    """
    Application-facing representation of a user's K-Means segment.
    """

    user_id: int
    cluster_id: int
    profile_name: str
    dominant_domain: str
    model_version: str
    selected_k: int
    domain_scores: dict[str, float]
    feature_strengths: dict[str, float]


def _validate_model_structure(
    model,
    scaler,
    metadata: dict,
    cluster_id: int,
) -> None:
    """
    Validate consistency between the persisted K-Means model,
    scaler, and metadata.
    """

    if not hasattr(model, "cluster_centers_"):
        raise UserSegmentProfileError(
            "Persisted K-Means model does not contain cluster centers."
        )

    cluster_centers = model.cluster_centers_

    if not isinstance(cluster_centers, np.ndarray):
        raise UserSegmentProfileError(
            "Persisted K-Means cluster centers are invalid."
        )

    if cluster_centers.ndim != 2:
        raise UserSegmentProfileError(
            "Persisted K-Means cluster centers must be a 2-D array."
        )

    if not hasattr(scaler, "mean_"):
        raise UserSegmentProfileError(
            "Persisted StandardScaler does not contain population means."
        )

    if not isinstance(scaler.mean_, np.ndarray):
        raise UserSegmentProfileError(
            "Persisted StandardScaler population means are invalid."
        )

    if "features" not in metadata:
        raise UserSegmentProfileError(
            "K-Means metadata does not contain a feature schema."
        )

    if not isinstance(metadata["features"], list):
        raise UserSegmentProfileError(
            "K-Means metadata feature schema must be a list."
        )

    feature_count = len(metadata["features"])

    model_cluster_count = cluster_centers.shape[0]
    model_feature_count = cluster_centers.shape[1]

    if model_feature_count != feature_count:
        raise UserSegmentProfileError(
            "K-Means cluster-center feature count does not match "
            "the metadata feature schema."
        )

    if len(scaler.mean_) != feature_count:
        raise UserSegmentProfileError(
            "StandardScaler population means do not match "
            "the metadata feature schema."
        )

    if not (
        0 <= cluster_id < model_cluster_count
    ):
        raise UserSegmentProfileError(
            "Predicted K-Means cluster ID is outside "
            "the valid cluster range."
        )

    if "selected_k" not in metadata:
        raise UserSegmentProfileError(
            "K-Means metadata does not contain selected_k."
        )

    try:
        selected_k = int(metadata["selected_k"])
    except (TypeError, ValueError) as exc:
        raise UserSegmentProfileError(
            "K-Means metadata selected_k is invalid."
        ) from exc

    if selected_k != model_cluster_count:
        raise UserSegmentProfileError(
            "K-Means metadata selected_k does not match "
            "the persisted model cluster count."
        )


def get_user_segment_profile(
    user_id: int,
) -> UserSegmentProfile:
    """
    Generate the complete application-facing segment profile
    for a CarbonIQ user.
    """

    try:
        segmentation_result = predict_user_segment(
            user_id
        )
    except (MLDataError, SegmentationPredictionError) as exc:
        raise UserSegmentProfileError(
            "Unable to generate the user's segment profile: "
            f"{exc}"
        ) from exc

    try:
        bundle = load_kmeans_model()
        metadata = load_kmeans_metadata()

    except ModelPersistenceError as exc:
        raise UserSegmentProfileError(
            "Unable to load K-Means segmentation artifacts: "
            f"{exc}"
        ) from exc

    model = bundle["model"]
    scaler = bundle["scaler"]

    _validate_model_structure(
        model=model,
        scaler=scaler,
        metadata=metadata,
        cluster_id=segmentation_result.cluster_id,
    )

    expected_features = tuple(
        metadata["features"]
    )

    try:
        scaled_centroid = model.cluster_centers_[
            segmentation_result.cluster_id
        ]

        original_centroid = scaler.inverse_transform(
            [scaled_centroid]
        )[0]

    except Exception as exc:
        raise UserSegmentProfileError(
            "Failed to convert the K-Means cluster centroid "
            "to the original feature scale."
        ) from exc

    centroid = {
        feature_name: float(value)
        for feature_name, value in zip(
            expected_features,
            original_centroid,
        )
    }

    population_means = {
        feature_name: float(mean_value)
        for feature_name, mean_value in zip(
            expected_features,
            scaler.mean_,
        )
    }

    try:
        cluster_profile = interpret_cluster(
            cluster_id=segmentation_result.cluster_id,
            centroid=centroid,
            population_means=population_means,
        )

    except ClusterInterpretationError as exc:
        raise UserSegmentProfileError(
            "Unable to interpret the user's K-Means cluster: "
            f"{exc}"
        ) from exc

    except Exception as exc:
        raise UserSegmentProfileError(
            "Unexpected error during K-Means cluster interpretation."
        ) from exc

    return UserSegmentProfile(
        user_id=segmentation_result.user_id,
        cluster_id=segmentation_result.cluster_id,
        profile_name=cluster_profile.profile_name,
        dominant_domain=cluster_profile.dominant_domain,
        model_version=segmentation_result.model_version,
        selected_k=segmentation_result.selected_k,
        domain_scores=dict(
            cluster_profile.domain_scores
        ),
        feature_strengths=dict(
            cluster_profile.feature_strengths
        ),
    )