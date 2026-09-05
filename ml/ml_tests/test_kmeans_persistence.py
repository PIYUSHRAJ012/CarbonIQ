from pathlib import Path
from tempfile import TemporaryDirectory
from unittest import TestCase
from unittest.mock import patch

import numpy as np
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from ml.services.model_persistence import (
    ModelPersistenceError,
    load_kmeans_model,
    load_kmeans_metadata,
    save_kmeans_model,
)


class KMeansPersistenceTests(TestCase):
    """Tests for K-Means model, scaler, and metadata persistence."""

    def setUp(self):
        self.scaler = StandardScaler()

        X = np.array(
            [
                [10.0, 20.0],
                [12.0, 22.0],
                [100.0, 200.0],
                [105.0, 210.0],
                [200.0, 400.0],
                [205.0, 410.0],
            ]
        )

        X_scaled = self.scaler.fit_transform(X)

        self.model = KMeans(
            n_clusters=3,
            random_state=42,
            n_init=20,
        )

        self.model.fit(X_scaled)

        self.metadata = {
            "model_version": "kmeans-v1",
            "features": [
                "electricity",
                "transportation",
                "avg_total_emission",
                "submission_count",
            ],
            "user_count": 6,
            "selected_k": 3,
            "candidate_scores": {
                "2": 0.61,
                "3": 0.78,
                "4": 0.55,
                "5": 0.42,
            },
            "silhouette_score": 0.78,
            "cluster_sizes": {
                "0": 2,
                "1": 2,
                "2": 2,
            },
        }

    def create_bundle(self):
        """
        Create the object that will be persisted as one artifact.
        """

        return {
            "model": self.model,
            "scaler": self.scaler,
        }

    def test_model_and_scaler_are_saved(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                model_path, metadata_path = save_kmeans_model(
                    model=self.model,
                    scaler=self.scaler,
                    metadata=self.metadata,
                )

            self.assertTrue(model_path.exists())
            self.assertTrue(metadata_path.exists())

    def test_saved_model_bundle_can_be_loaded(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_kmeans_model(
                    model=self.model,
                    scaler=self.scaler,
                    metadata=self.metadata,
                )

                bundle = load_kmeans_model()

            self.assertIsInstance(
                bundle,
                dict,
            )

            self.assertIsInstance(
                bundle["model"],
                KMeans,
            )

            self.assertIsInstance(
                bundle["scaler"],
                StandardScaler,
            )

    def test_loaded_bundle_produces_cluster_predictions(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            X = np.array(
                [
                    [11.0, 21.0],
                    [102.0, 205.0],
                    [202.0, 405.0],
                ]
            )

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_kmeans_model(
                    model=self.model,
                    scaler=self.scaler,
                    metadata=self.metadata,
                )

                bundle = load_kmeans_model()

            scaled_X = bundle["scaler"].transform(X)

            labels = bundle["model"].predict(
                scaled_X
            )

            self.assertEqual(
                len(labels),
                3,
            )

            self.assertTrue(
                np.isfinite(labels).all()
            )

    def test_scaler_preserves_transformation_after_loading(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            X = np.array(
                [
                    [11.0, 21.0],
                    [102.0, 205.0],
                    [202.0, 405.0],
                ]
            )

            original_scaled = self.scaler.transform(X)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_kmeans_model(
                    model=self.model,
                    scaler=self.scaler,
                    metadata=self.metadata,
                )

                bundle = load_kmeans_model()

            loaded_scaled = bundle["scaler"].transform(X)

            np.testing.assert_array_equal(
                original_scaled,
                loaded_scaled,
            )

    def test_metadata_can_be_loaded(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                save_kmeans_model(
                    model=self.model,
                    scaler=self.scaler,
                    metadata=self.metadata,
                )

                loaded_metadata = load_kmeans_metadata()

            self.assertEqual(
                loaded_metadata,
                self.metadata,
            )

    def test_missing_kmeans_model_raises_error(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    load_kmeans_model()

    def test_missing_kmeans_metadata_raises_error(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    load_kmeans_metadata()

    def test_invalid_kmeans_model_is_rejected(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    save_kmeans_model(
                        model="not-a-kmeans-model",
                        scaler=self.scaler,
                        metadata=self.metadata,
                    )

    def test_invalid_scaler_is_rejected(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            with patch(
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    save_kmeans_model(
                        model=self.model,
                        scaler="not-a-scaler",
                        metadata=self.metadata,
                    )

    def test_invalid_metadata_json_is_rejected(self):
        with TemporaryDirectory() as temp_directory:
            artifacts_directory = Path(temp_directory)

            metadata_path = (
                artifacts_directory
                / "user_segmenter_metadata.json"
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
                "ml.services.model_persistence."
                "get_ml_artifacts_directory",
                return_value=artifacts_directory,
            ):
                with self.assertRaises(ModelPersistenceError):
                    load_kmeans_metadata()