from __future__ import annotations

from dataclasses import dataclass
from math import ceil

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score

from ml.services.feature_engineering import (
    MLDataError,
    get_temporal_prediction_dataset,
)


RANDOM_STATE = 42
TEST_SIZE = 0.20
N_ESTIMATORS = 200

MINIMUM_TRANSITIONS = 30
MINIMUM_USERS = 5


@dataclass(frozen=True)
class RandomForestTrainingResult:
    """
    Container for the output of a Random Forest training run.
    """

    model: RandomForestRegressor
    feature_names: tuple[str, ...]
    sample_count: int
    training_samples: int
    test_samples: int
    user_count: int
    training_period_start: str
    training_period_end: str
    test_period_start: str
    test_period_end: str
    mae: float
    rmse: float
    r2: float


def validate_training_data(
    X: pd.DataFrame,
    y: pd.Series,
    metadata: pd.DataFrame,
    minimum_transitions: int = MINIMUM_TRANSITIONS,
    minimum_users: int = MINIMUM_USERS,
) -> None:
    """
    Validate a temporal Random Forest training dataset.
    """

    if X.empty or y.empty or metadata.empty:
        raise MLDataError(
            "The Random Forest temporal training dataset is empty."
        )

    if not (
        len(X) == len(y) == len(metadata)
    ):
        raise MLDataError(
            "Features, target, and metadata have different row counts."
        )

    if len(X) < minimum_transitions:
        raise MLDataError(
            f"At least {minimum_transitions} temporal training transitions "
            f"are required for Random Forest training. Found {len(X)}."
        )

    required_metadata_columns = {
        "user_id",
        "feature_period",
        "target_period",
    }

    missing_metadata_columns = (
        required_metadata_columns - set(metadata.columns)
    )

    if missing_metadata_columns:
        raise MLDataError(
            "Random Forest metadata is missing required columns: "
            f"{sorted(missing_metadata_columns)}."
        )

    unique_users = metadata["user_id"].nunique()

    if unique_users < minimum_users:
        raise MLDataError(
            f"At least {minimum_users} distinct users are required "
            f"for Random Forest training. Found {unique_users}."
        )

    if X.isnull().values.any():
        raise MLDataError(
            "The Random Forest feature matrix contains missing values."
        )

    if y.isnull().any():
        raise MLDataError(
            "The Random Forest target contains missing values."
        )

    if metadata[
        ["user_id", "feature_period", "target_period"]
    ].isnull().values.any():
        raise MLDataError(
            "Random Forest metadata contains missing values."
        )

    if (
        metadata["target_period"]
        <= metadata["feature_period"]
    ).any():
        raise MLDataError(
            "Every target period must be later than its feature period."
        )

    unique_target_periods = metadata["target_period"].nunique()

    if unique_target_periods < 2:
        raise MLDataError(
            "At least two target periods are required for "
            "chronological train/test evaluation."
        )


def chronological_train_test_split(
    X: pd.DataFrame,
    y: pd.Series,
    metadata: pd.DataFrame,
    test_size: float = TEST_SIZE,
):
    """
    Split temporal training data chronologically.

    The latest target periods are reserved for testing.
    """

    if not 0 < test_size < 1:
        raise ValueError(
            "test_size must be between 0 and 1."
        )

    ordered_metadata = metadata.sort_values(
        by="target_period"
    ).reset_index()

    unique_periods = (
        ordered_metadata["target_period"]
        .drop_duplicates()
        .tolist()
    )

    test_period_count = max(
        1,
        ceil(len(unique_periods) * test_size),
    )

    if test_period_count >= len(unique_periods):
        test_period_count = len(unique_periods) - 1

    test_periods = set(
        unique_periods[-test_period_count:]
    )

    train_mask = ~metadata["target_period"].isin(
        test_periods
    )

    test_mask = metadata["target_period"].isin(
        test_periods
    )

    if not train_mask.any():
        raise MLDataError(
            "Chronological split produced no training samples."
        )

    if not test_mask.any():
        raise MLDataError(
            "Chronological split produced no test samples."
        )

    X_train = X.loc[train_mask].reset_index(drop=True)
    X_test = X.loc[test_mask].reset_index(drop=True)

    y_train = y.loc[train_mask].reset_index(drop=True)
    y_test = y.loc[test_mask].reset_index(drop=True)

    metadata_train = metadata.loc[
        train_mask
    ].reset_index(drop=True)

    metadata_test = metadata.loc[
        test_mask
    ].reset_index(drop=True)

    return (
        X_train,
        X_test,
        y_train,
        y_test,
        metadata_train,
        metadata_test,
    )


def train_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
    metadata: pd.DataFrame,
) -> RandomForestTrainingResult:
    """
    Train and evaluate the temporal Random Forest regressor.
    """

    validate_training_data(
        X,
        y,
        metadata,
    )

    (
        X_train,
        X_test,
        y_train,
        y_test,
        metadata_train,
        metadata_test,
    ) = chronological_train_test_split(
        X,
        y,
        metadata,
    )

    model = RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
    )

    model.fit(
        X_train,
        y_train,
    )

    predictions = model.predict(
        X_test
    )

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    mse = mean_squared_error(
        y_test,
        predictions,
    )

    rmse = mse ** 0.5

    r2 = r2_score(
        y_test,
        predictions,
    )

    train_periods = metadata_train["target_period"]

    test_periods = metadata_test["target_period"]

    return RandomForestTrainingResult(
        model=model,
        feature_names=tuple(X.columns),
        sample_count=len(X),
        training_samples=len(X_train),
        test_samples=len(X_test),
        user_count=metadata["user_id"].nunique(),
        training_period_start=str(train_periods.min()),
        training_period_end=str(train_periods.max()),
        test_period_start=str(test_periods.min()),
        test_period_end=str(test_periods.max()),
        mae=float(mae),
        rmse=float(rmse),
        r2=float(r2),
    )


def train_random_forest_from_database() -> RandomForestTrainingResult:
    """
    Build the temporal prediction dataset from PostgreSQL
    and train the Random Forest model.
    """

    X, y, metadata = get_temporal_prediction_dataset()

    return train_random_forest(
        X,
        y,
        metadata,
    )