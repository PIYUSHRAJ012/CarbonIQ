from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import joblib
from sklearn.ensemble import RandomForestRegressor

from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

class ModelPersistenceError(Exception):
    """Raised when a model artifact cannot be saved or loaded."""


def get_ml_artifacts_directory() -> Path:
    """
    Return the directory used for ML-generated artifacts.
    """

    project_root = Path(__file__).resolve().parents[2]
    artifacts_directory = project_root / "artifacts" / "ml"

    artifacts_directory.mkdir(
        parents=True,
        exist_ok=True,
    )

    return artifacts_directory


def save_random_forest_model(
    model: RandomForestRegressor,
    metadata: dict[str, Any],
    model_filename: str = "carbon_predictor.joblib",
    metadata_filename: str = "carbon_predictor_metadata.json",
) -> tuple[Path, Path]:
    """
    Persist a trained Random Forest model and its metadata.

    Returns:
        Tuple containing:
            - model artifact path
            - metadata artifact path
    """

    if not isinstance(model, RandomForestRegressor):
        raise ModelPersistenceError(
            "Only RandomForestRegressor models can be saved "
            "by this function."
        )

    artifacts_directory = get_ml_artifacts_directory()

    model_path = artifacts_directory / model_filename
    metadata_path = artifacts_directory / metadata_filename

    try:
        joblib.dump(
            model,
            model_path,
        )

        with metadata_path.open(
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(
                metadata,
                metadata_file,
                indent=4,
                default=str,
            )

    except (OSError, TypeError, ValueError) as exc:
        raise ModelPersistenceError(
            f"Failed to save Random Forest artifacts: {exc}"
        ) from exc

    return model_path, metadata_path


def load_random_forest_model(
    model_filename: str = "carbon_predictor.joblib",
) -> RandomForestRegressor:
    """
    Load a persisted Random Forest model.
    """

    model_path = (
        get_ml_artifacts_directory()
        / model_filename
    )

    if not model_path.exists():
        raise ModelPersistenceError(
            f"Random Forest model artifact not found: {model_path}"
        )

    try:
        model = joblib.load(model_path)

    except (OSError, ValueError, EOFError) as exc:
        raise ModelPersistenceError(
            f"Failed to load Random Forest model: {exc}"
        ) from exc

    if not isinstance(model, RandomForestRegressor):
        raise ModelPersistenceError(
            "Loaded artifact is not a RandomForestRegressor."
        )

    return model


def load_random_forest_metadata(
    metadata_filename: str = "carbon_predictor_metadata.json",
) -> dict[str, Any]:
    """
    Load metadata associated with the persisted Random Forest model.
    """

    metadata_path = (
        get_ml_artifacts_directory()
        / metadata_filename
    )

    if not metadata_path.exists():
        raise ModelPersistenceError(
            f"Random Forest metadata artifact not found: {metadata_path}"
        )

    try:
        with metadata_path.open(
            "r",
            encoding="utf-8",
        ) as metadata_file:
            metadata = json.load(metadata_file)

    except (OSError, json.JSONDecodeError) as exc:
        raise ModelPersistenceError(
            f"Failed to load Random Forest metadata: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise ModelPersistenceError(
            "Random Forest metadata must be a JSON object."
        )

    return metadata

def save_kmeans_model(
    model: KMeans,
    scaler: StandardScaler,
    metadata: dict[str, Any],
    model_filename: str = "user_segmenter.joblib",
    metadata_filename: str = "user_segmenter_metadata.json",
) -> tuple[Path, Path]:
    """
    Persist a K-Means model together with its fitted StandardScaler
    and associated metadata.
    """

    if not isinstance(model, KMeans):
        raise ModelPersistenceError(
            "Only KMeans models can be saved by this function."
        )

    if not isinstance(scaler, StandardScaler):
        raise ModelPersistenceError(
            "Only StandardScaler instances can be saved "
            "by this function."
        )

    artifacts_directory = get_ml_artifacts_directory()

    model_path = artifacts_directory / model_filename
    metadata_path = artifacts_directory / metadata_filename

    bundle = {
        "model": model,
        "scaler": scaler,
    }

    try:
        joblib.dump(
            bundle,
            model_path,
        )

        with metadata_path.open(
            "w",
            encoding="utf-8",
        ) as metadata_file:
            json.dump(
                metadata,
                metadata_file,
                indent=4,
                default=str,
            )

    except (OSError, TypeError, ValueError) as exc:
        raise ModelPersistenceError(
            f"Failed to save K-Means artifacts: {exc}"
        ) from exc

    return model_path, metadata_path


def load_kmeans_model(
    model_filename: str = "user_segmenter.joblib",
) -> dict[str, Any]:
    """
    Load the persisted K-Means model bundle.

    Returns:
        Dictionary containing:
            - model: KMeans
            - scaler: StandardScaler
    """

    model_path = (
        get_ml_artifacts_directory()
        / model_filename
    )

    if not model_path.exists():
        raise ModelPersistenceError(
            f"K-Means model artifact not found: {model_path}"
        )

    try:
        bundle = joblib.load(model_path)

    except (OSError, ValueError, EOFError) as exc:
        raise ModelPersistenceError(
            f"Failed to load K-Means model: {exc}"
        ) from exc

    if not isinstance(bundle, dict):
        raise ModelPersistenceError(
            "K-Means model artifact must contain a dictionary bundle."
        )

    if not isinstance(
        bundle.get("model"),
        KMeans,
    ):
        raise ModelPersistenceError(
            "K-Means artifact does not contain a valid KMeans model."
        )

    if not isinstance(
        bundle.get("scaler"),
        StandardScaler,
    ):
        raise ModelPersistenceError(
            "K-Means artifact does not contain a valid StandardScaler."
        )

    return bundle


def load_kmeans_metadata(
    metadata_filename: str = "user_segmenter_metadata.json",
) -> dict[str, Any]:
    """
    Load metadata associated with the persisted K-Means model.
    """

    metadata_path = (
        get_ml_artifacts_directory()
        / metadata_filename
    )

    if not metadata_path.exists():
        raise ModelPersistenceError(
            f"K-Means metadata artifact not found: {metadata_path}"
        )

    try:
        with metadata_path.open(
            "r",
            encoding="utf-8",
        ) as metadata_file:
            metadata = json.load(metadata_file)

    except (OSError, json.JSONDecodeError) as exc:
        raise ModelPersistenceError(
            f"Failed to load K-Means metadata: {exc}"
        ) from exc

    if not isinstance(metadata, dict):
        raise ModelPersistenceError(
            "K-Means metadata must be a JSON object."
        )

    return metadata