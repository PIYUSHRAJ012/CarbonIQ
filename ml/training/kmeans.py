from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler

from ml.services.feature_engineering import (
    MLDataError,
    get_segmentation_dataset,
)


RANDOM_STATE = 42
N_INIT = 20

MIN_K = 2
MAX_K = 5

MINIMUM_USERS = 10


@dataclass(frozen=True)
class KMeansTrainingResult:
    """
    Container for the output of a K-Means training run.
    """

    model: KMeans
    scaler: StandardScaler
    feature_names: tuple[str, ...]
    user_count: int
    selected_k: int
    candidate_scores: dict[int, float]
    silhouette_score: float
    labels: np.ndarray
    cluster_sizes: dict[int, int]


def validate_segmentation_data(
    X: pd.DataFrame,
    metadata: pd.DataFrame,
    minimum_users: int = MINIMUM_USERS,
) -> None:
    """
    Validate the user-level dataset before K-Means training.
    """

    if X.empty or metadata.empty:
        raise MLDataError(
            "The K-Means segmentation dataset is empty."
        )

    if len(X) != len(metadata):
        raise MLDataError(
            "Features and metadata have different row counts."
        )

    if len(X) < minimum_users:
        raise MLDataError(
            f"At least {minimum_users} users are required "
            f"for K-Means segmentation. Found {len(X)}."
        )

    if "user_id" not in metadata.columns:
        raise MLDataError(
            "K-Means metadata must contain a 'user_id' column."
        )

    if "user_id" in X.columns:
        raise MLDataError(
            "user_id must not be included in K-Means features."
        )

    if X.isnull().values.any():
        raise MLDataError(
            "The K-Means feature matrix contains missing values."
        )

    if metadata["user_id"].isnull().any():
        raise MLDataError(
            "K-Means metadata contains missing user IDs."
        )

    if metadata["user_id"].nunique() != len(metadata):
        raise MLDataError(
            "Each K-Means row must represent a unique user."
        )

    if X.shape[1] < MIN_K:
        raise MLDataError(
            "The K-Means feature matrix does not contain enough "
            "features for clustering."
        )

    if not all(
        pd.api.types.is_numeric_dtype(dtype)
        for dtype in X.dtypes
    ):
        raise MLDataError(
            "All K-Means features must be numeric."
        )


def _get_valid_k_values(
    user_count: int,
    min_k: int = MIN_K,
    max_k: int = MAX_K,
) -> list[int]:
    """
    Return candidate K values valid for the current user count.
    """

    if min_k < 2:
        raise MLDataError(
            "K-Means requires a minimum K of at least 2."
        )

    if max_k < min_k:
        raise MLDataError(
            "K-Means max_k cannot be smaller than min_k."
        )

    if user_count < 2:
        raise MLDataError(
            "At least two users are required for K-Means clustering."
        )

    upper_bound = min(
        max_k,
        user_count - 1,
    )

    if min_k > upper_bound:
        raise MLDataError(
            "No valid K values are available for the current "
            "number of users."
        )

    return list(
        range(
            min_k,
            upper_bound + 1,
        )
    )


def evaluate_k_values(
    X: pd.DataFrame,
    min_k: int = MIN_K,
    max_k: int = MAX_K,
) -> dict[int, float]:
    """
    Evaluate candidate K values using Silhouette Score.

    The input data is standardized before clustering.
    """

    if X.empty:
        raise MLDataError(
            "Cannot evaluate K-Means on an empty dataset."
        )

    if X.isnull().values.any():
        raise MLDataError(
            "Cannot evaluate K-Means with missing feature values."
        )

    user_count = len(X)

    candidate_k_values = _get_valid_k_values(
        user_count=user_count,
        min_k=min_k,
        max_k=max_k,
    )

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(X)

    scores: dict[int, float] = {}

    for k in candidate_k_values:
        model = KMeans(
            n_clusters=k,
            random_state=RANDOM_STATE,
            n_init=N_INIT,
        )

        labels = model.fit_predict(
            X_scaled
        )

        score = silhouette_score(
            X_scaled,
            labels,
        )

        scores[k] = float(score)

    return scores


def train_kmeans(
    X: pd.DataFrame,
    metadata: pd.DataFrame,
) -> KMeansTrainingResult:
    """
    Train the final K-Means segmentation model.

    The best K is selected using the highest Silhouette Score.
    """

    validate_segmentation_data(
        X,
        metadata,
    )

    scaler = StandardScaler()

    X_scaled = scaler.fit_transform(
        X
    )

    candidate_scores = evaluate_k_values(
        X,
        min_k=MIN_K,
        max_k=MAX_K,
    )

    selected_k = max(
        candidate_scores,
        key=candidate_scores.get,
    )

    model = KMeans(
        n_clusters=selected_k,
        random_state=RANDOM_STATE,
        n_init=N_INIT,
    )

    labels = model.fit_predict(
        X_scaled
    )

    final_silhouette_score = silhouette_score(
        X_scaled,
        labels,
    )

    unique_labels, counts = np.unique(
        labels,
        return_counts=True,
    )

    cluster_sizes = {
        int(label): int(count)
        for label, count in zip(
            unique_labels,
            counts,
        )
    }

    return KMeansTrainingResult(
        model=model,
        scaler=scaler,
        feature_names=tuple(X.columns),
        user_count=len(X),
        selected_k=selected_k,
        candidate_scores=candidate_scores,
        silhouette_score=float(
            final_silhouette_score
        ),
        labels=labels,
        cluster_sizes=cluster_sizes,
    )


def train_kmeans_from_database() -> KMeansTrainingResult:
    """
    Build the user-level segmentation dataset from PostgreSQL
    and train the K-Means model.
    """

    X, metadata = get_segmentation_dataset()

    return train_kmeans(
        X,
        metadata,
    )