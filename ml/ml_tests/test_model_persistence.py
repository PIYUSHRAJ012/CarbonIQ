from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import numpy as np
from sklearn.ensemble import RandomForestRegressor

from ml.services.model_persistence import (
    ModelPersistenceError,
    load_random_forest_metadata,
    load_random_forest_model,
    save_random_forest_model,
)


class ModelPersistenceTests(TestCase):
    """Tests for Random Forest model and metadata persistence."""

    def setUp(self):
        self.model = RandomForestRegressor(
            n_estimators=10,
            random_state=42,
        )

        X = np.array(
            [
                [100.0, 50.0],
                [200.0, 80.0],
                [150.0, 60.0],
                [300.0, 100.0],
            ]
        )

        y = np.array(
            [
                80.0,
                120.0,
                100.0,
                180.0,
            ]
        )

        self.model.fit(X, y)

        self.metadata = {
            "model_version": "rf-v1",
            "target": "total_emission",
            "features": [
                "electricity",
                "transportation",
            ],
            "sample_count": 4,
            "training_samples": 3,
            "test_samples": 1,
            "mae": 10.5,
            "rmse": 14.2,
            "r2": 0.85,
        }

    def test_model_and_metadata_are_saved(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                model_path, metadata_path = save_random_forest_model(
                    self.model,
                    self.metadata,
                )

            self.assertTrue(model_path.exists())
            self.assertTrue(metadata_path.exists())

    def test_saved_model_can_be_loaded(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_random_forest_model(
                    self.model,
                    self.metadata,
                )

                loaded_model = load_random_forest_model()

            self.assertIsInstance(
                loaded_model,
                RandomForestRegressor,
            )

    def test_loaded_model_produces_predictions(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            X = np.array(
                [
                    [100.0, 50.0],
                    [200.0, 80.0],
                ]
            )

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_random_forest_model(
                    self.model,
                    self.metadata,
                )

                loaded_model = load_random_forest_model()

            predictions = loaded_model.predict(X)

            self.assertEqual(
                len(predictions),
                2,
            )

            self.assertTrue(
                np.isfinite(predictions).all()
            )

    def test_metadata_can_be_loaded(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_random_forest_model(
                    self.model,
                    self.metadata,
                )

                loaded_metadata = load_random_forest_metadata()

            self.assertEqual(
                loaded_metadata,
                self.metadata,
            )

    def test_missing_model_raises_error(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    load_random_forest_model()

    def test_missing_metadata_raises_error(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    load_random_forest_metadata()

    def test_invalid_model_type_is_rejected(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    save_random_forest_model(
                        "not-a-random-forest",
                        self.metadata,
                    )

    def test_invalid_metadata_json_is_rejected(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)
            metadata_path = (
                artifacts_directory
                / "carbon_predictor_metadata.json"
            )

            artifacts_directory.mkdir(
                parents=True,
                exist_ok=True,
            )

            metadata_path.write_text(
                "{invalid-json",
                encoding="utf-8",
            )

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    load_random_forest_metadata()

    def test_saved_model_preserves_predictions(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            X = np.array(
                [
                    [120.0, 40.0],
                    [250.0, 90.0],
                ]
            )

            original_predictions = self.model.predict(X)

            with patch(
                "ml.services.model_persistence.get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_random_forest_model(
                    self.model,
                    self.metadata,
                )

                loaded_model = load_random_forest_model()

            loaded_predictions = loaded_model.predict(X)

            np.testing.assert_array_equal(
                original_predictions,
                loaded_predictions,
            )