from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from ml.services.feature_engineering import MLDataError
from ml.services.model_persistence import (
    ModelPersistenceError,
)
from ml.services.segmentation import (
    SegmentationPredictionError,
    predict_user_segment,
)


class SegmentationPredictionTests(TestCase):
    """Tests for K-Means user-segment inference."""

    def setUp(self):
        self.user_id = 1

        self.feature_names = (
            "electricity",
            "transportation",
            "avg_total_emission",
            "submission_count",
        )

        self.X = pd.DataFrame(
            {
                "electricity": [100.0],
                "transportation": [50.0],
                "avg_total_emission": [80.0],
                "submission_count": [2.0],
            }
        )

        self.metadata = {
            "model_version": "kmeans-v1",
            "features": list(self.feature_names),
            "user_count": 20,
            "selected_k": 3,
            "candidate_scores": {
                "2": 0.51,
                "3": 0.68,
                "4": 0.57,
                "5": 0.44,
            },
            "silhouette_score": 0.68,
            "cluster_sizes": {
                "0": 7,
                "1": 6,
                "2": 7,
            },
        }

        self.scaler = StandardScaler()

        training_data = pd.DataFrame(
            [
                [10.0, 10.0, 20.0, 1.0],
                [12.0, 12.0, 22.0, 1.0],
                [100.0, 100.0, 200.0, 2.0],
                [105.0, 105.0, 210.0, 2.0],
                [200.0, 200.0, 400.0, 3.0],
                [205.0, 205.0, 410.0, 3.0],
            ],
            columns=self.feature_names,
        )

        scaled_training_data = self.scaler.fit_transform(
            training_data
        )

        self.model = KMeans(
            n_clusters=3,
            random_state=42,
            n_init=20,
        )

        self.model.fit(
            scaled_training_data
        )

    def test_predict_returns_result(self):
        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            return_value={
                "model": self.model,
                "scaler": self.scaler,
            },
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ):
            result = predict_user_segment(
                user_id=self.user_id
            )

        self.assertEqual(
            result.user_id,
            self.user_id,
        )

        self.assertIsInstance(
            result.cluster_id,
            int,
        )

        self.assertEqual(
            result.model_version,
            "kmeans-v1",
        )

        self.assertEqual(
            result.selected_k,
            3,
        )

    def test_prediction_uses_loaded_scaler_and_model(self):
        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            return_value={
                "model": self.model,
                "scaler": self.scaler,
            },
        ) as mock_load_model, patch(
            "ml.services.segmentation."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ):
            result = predict_user_segment(
                user_id=self.user_id
            )

        mock_load_model.assert_called_once()

        self.assertGreaterEqual(
            result.cluster_id,
            0,
        )

        self.assertLess(
            result.cluster_id,
            3,
        )

    def test_feature_schema_mismatch_is_rejected(self):
        incorrect_metadata = dict(
            self.metadata
        )

        incorrect_metadata["features"] = [
            "electricity",
            "food",
            "transportation",
        ]

        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            return_value={
                "model": self.model,
                "scaler": self.scaler,
            },
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_metadata",
            return_value=incorrect_metadata,
        ):
            with self.assertRaises(
                SegmentationPredictionError
            ):
                predict_user_segment(
                    user_id=self.user_id
                )

    def test_feature_order_mismatch_is_rejected(self):
        incorrect_metadata = dict(
            self.metadata
        )

        incorrect_metadata["features"] = [
            "transportation",
            "electricity",
            "avg_total_emission",
            "submission_count",
        ]

        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            return_value={
                "model": self.model,
                "scaler": self.scaler,
            },
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_metadata",
            return_value=incorrect_metadata,
        ):
            with self.assertRaises(
                SegmentationPredictionError
            ):
                predict_user_segment(
                    user_id=self.user_id
                )

    def test_missing_model_is_converted_to_prediction_error(self):
        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            side_effect=ModelPersistenceError(
                "K-Means model artifact not found."
            ),
        ):
            with self.assertRaises(
                SegmentationPredictionError
            ):
                predict_user_segment(
                    user_id=self.user_id
                )

    def test_missing_metadata_is_converted_to_prediction_error(self):
        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            return_value={
                "model": self.model,
                "scaler": self.scaler,
            },
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_metadata",
            side_effect=ModelPersistenceError(
                "K-Means metadata artifact not found."
            ),
        ):
            with self.assertRaises(
                SegmentationPredictionError
            ):
                predict_user_segment(
                    user_id=self.user_id
                )

    def test_user_without_features_propagates_ml_data_error(self):
        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            side_effect=MLDataError(
                "No completed carbon activities."
            ),
        ):
            with self.assertRaises(
                MLDataError
            ):
                predict_user_segment(
                    user_id=self.user_id
                )

    def test_cluster_id_is_not_exposed_as_semantic_label(self):
        with patch(
            "ml.services.segmentation."
            "get_user_segmentation_features",
            return_value=(
                self.X,
                pd.DataFrame(
                    [
                        {
                            "user_id": self.user_id,
                        }
                    ]
                ),
            ),
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_model",
            return_value={
                "model": self.model,
                "scaler": self.scaler,
            },
        ), patch(
            "ml.services.segmentation."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ):
            result = predict_user_segment(
                user_id=self.user_id
            )

        self.assertIsInstance(
            result.cluster_id,
            int,
        )

        self.assertNotIn(
            "label",
            result.__dict__,
        )