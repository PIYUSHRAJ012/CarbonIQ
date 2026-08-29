from __future__ import annotations

from dataclasses import dataclass

import pandas as pd
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error, r2_score
from sklearn.model_selection import train_test_split

from ml.services.feature_engineering import MLDataError, get_prediction_dataset


RANDOM_STATE = 42
TEST_SIZE = 0.20
N_ESTIMATORS = 200
MINIMUM_SAMPLES = 30


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
    mae: float
    rmse: float
    r2: float


def validate_training_data(
    X: pd.DataFrame,
    y: pd.Series,
    minimum_samples: int = MINIMUM_SAMPLES,
) -> None:
    """
    Validate that the dataset is suitable for baseline training.
    """

    if X.empty or y.empty:
        raise MLDataError(
            "The Random Forest training dataset is empty."
        )

    if len(X) != len(y):
        raise MLDataError(
            "Feature matrix and target vector have different row counts."
        )

    if len(X) < minimum_samples:
        raise MLDataError(
            f"At least {minimum_samples} completed submissions are required "
            f"for Random Forest training. Found {len(X)}."
        )

    if X.isnull().values.any():
        raise MLDataError(
            "The Random Forest feature matrix contains missing values."
        )

    if y.isnull().any():
        raise MLDataError(
            "The Random Forest target contains missing values."
        )


def train_random_forest(
    X: pd.DataFrame,
    y: pd.Series,
) -> RandomForestTrainingResult:
    """
    Train and evaluate the baseline Random Forest regressor.

    The function does not persist the trained model. Persistence will be
    handled separately after the training contract is verified.
    """

    validate_training_data(X, y)

    X_train, X_test, y_train, y_test = train_test_split(
        X,
        y,
        test_size=TEST_SIZE,
        random_state=RANDOM_STATE,
    )

    model = RandomForestRegressor(
        n_estimators=N_ESTIMATORS,
        random_state=RANDOM_STATE,
    )

    model.fit(X_train, y_train)

    predictions = model.predict(X_test)

    mae = mean_absolute_error(
        y_test,
        predictions,
    )

    rmse = mean_squared_error(
        y_test,
        predictions,
    ) ** 0.5

    r2 = r2_score(
        y_test,
        predictions,
    )

    return RandomForestTrainingResult(
        model=model,
        feature_names=tuple(X.columns),
        sample_count=len(X),
        training_samples=len(X_train),
        test_samples=len(X_test),
        mae=float(mae),
        rmse=float(rmse),
        r2=float(r2),
    )


def train_random_forest_from_database() -> RandomForestTrainingResult:
    """
    Build the prediction dataset from PostgreSQL and train the
    baseline Random Forest model.
    """

    X, y, _metadata = get_prediction_dataset()

    return train_random_forest(X, y)