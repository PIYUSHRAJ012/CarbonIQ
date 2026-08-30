from unittest import TestCase
from unittest.mock import patch

import numpy as np

from ml.services.segmentation import SegmentationResult
from ml.services.cluster_interpretation import ClusterProfile
from ml.services.segmentation_profile import (
    UserSegmentProfileError,
    get_user_segment_profile,
)


class UserSegmentProfileIntegrationTests(TestCase):
    """Tests for the application-facing user segment profile service."""

    def setUp(self):
        self.user_id = 1

        self.feature_names = [
            "electricity",
            "transportation",
            "avg_total_emission",
            "submission_count",
        ]

        self.segmentation_result = SegmentationResult(
            user_id=self.user_id,
            cluster_id=1,
            model_version="kmeans-v1",
            selected_k=3,
        )

        self.metadata = {
            "model_version": "kmeans-v1",
            "features": self.feature_names,
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

        self.cluster_profile = ClusterProfile(
            cluster_id=1,
            profile_name="Energy-oriented",
            dominant_domain="energy",
            domain_scores={
                "energy": 2.0,
                "transport": 1.0,
                "food": 1.0,
                "shopping": 1.0,
                "waste": 1.0,
            },
            feature_strengths={
                "electricity": 2.0,
            },
        )

    def create_mock_model(
        self,
        cluster_centers,
    ):
        return type(
            "MockModel",
            (),
            {
                "cluster_centers_": np.array(
                    cluster_centers,
                    dtype=float,
                )
            },
        )()

    def create_mock_scaler(
        self,
        mean_values=None,
        inverse_values=None,
    ):
        if mean_values is None:
            mean_values = [
                50.0,
                100.0,
                150.0,
                2.0,
            ]

        def inverse_transform(
            scaler,
            values,
        ):
            if inverse_values is not None:
                return np.array(
                    [inverse_values],
                    dtype=float,
                )

            return np.asarray(
                values,
                dtype=float,
            )

        return type(
            "MockScaler",
            (),
            {
                "mean_": np.array(
                    mean_values,
                    dtype=float,
                ),
                "inverse_transform": inverse_transform,
            },
        )()

    def test_returns_complete_user_segment_profile(self):
        model = self.create_mock_model(
            [
                [0.0, 0.0, 0.0, 0.0],
                [1.0, 2.0, 3.0, 4.0],
                [5.0, 5.0, 5.0, 5.0],
            ]
        )

        scaler = self.create_mock_scaler()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=self.segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ), patch(
            "ml.services.segmentation_profile."
            "interpret_cluster",
            return_value=self.cluster_profile,
        ) as mock_interpret:
            result = get_user_segment_profile(
                self.user_id
            )

        self.assertEqual(
            result.user_id,
            self.user_id,
        )

        self.assertEqual(
            result.cluster_id,
            1,
        )

        self.assertEqual(
            result.profile_name,
            "Energy-oriented",
        )

        self.assertEqual(
            result.dominant_domain,
            "energy",
        )

        self.assertEqual(
            result.model_version,
            "kmeans-v1",
        )

        self.assertEqual(
            result.selected_k,
            3,
        )

        mock_interpret.assert_called_once()

    def test_uses_correct_cluster_centroid(self):
        model = self.create_mock_model(
            [
                [10.0, 20.0, 30.0, 40.0],
                [100.0, 200.0, 300.0, 400.0],
                [500.0, 600.0, 700.0, 800.0],
            ]
        )

        scaler = self.create_mock_scaler()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=self.segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ), patch(
            "ml.services.segmentation_profile."
            "interpret_cluster",
            return_value=self.cluster_profile,
        ) as mock_interpret:
            get_user_segment_profile(
                self.user_id
            )

        kwargs = mock_interpret.call_args.kwargs

        self.assertEqual(
            kwargs["cluster_id"],
            1,
        )

        self.assertEqual(
            kwargs["centroid"],
            {
                "electricity": 100.0,
                "transportation": 200.0,
                "avg_total_emission": 300.0,
                "submission_count": 400.0,
            },
        )

    def test_feature_schema_from_metadata_is_used_for_centroid(self):
        segmentation_result = SegmentationResult(
            user_id=self.user_id,
            cluster_id=0,
            model_version="kmeans-v1",
            selected_k=2,
        )

        metadata = {
            **self.metadata,
            "features": [
                "transportation",
                "electricity",
            ],
            "selected_k": 2,
        }

        model = self.create_mock_model(
            [
                [20.0, 10.0],
                [50.0, 40.0],
            ]
        )

        scaler = self.create_mock_scaler(
            mean_values=[
                100.0,
                50.0,
            ]
        )

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=metadata,
        ), patch(
            "ml.services.segmentation_profile."
            "interpret_cluster",
            return_value=self.cluster_profile,
        ) as mock_interpret:
            get_user_segment_profile(
                self.user_id
            )

        kwargs = mock_interpret.call_args.kwargs

        self.assertEqual(
            kwargs["centroid"],
            {
                "transportation": 20.0,
                "electricity": 10.0,
            },
        )

        self.assertEqual(
            kwargs["population_means"],
            {
                "transportation": 100.0,
                "electricity": 50.0,
            },
        )

    def test_missing_cluster_centers_are_rejected(self):
        model = type(
            "MockModel",
            (),
            {}
        )()

        scaler = self.create_mock_scaler()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=self.segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ):
            with self.assertRaises(
                UserSegmentProfileError
            ):
                get_user_segment_profile(
                    self.user_id
                )

    def test_invalid_cluster_id_is_rejected(self):
        invalid_result = SegmentationResult(
            user_id=self.user_id,
            cluster_id=99,
            model_version="kmeans-v1",
            selected_k=3,
        )

        model = self.create_mock_model(
            [
                [0.0, 0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0, 2.0],
            ]
        )

        scaler = self.create_mock_scaler()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=invalid_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ):
            with self.assertRaises(
                UserSegmentProfileError
            ):
                get_user_segment_profile(
                    self.user_id
                )

    def test_selected_k_must_match_model_cluster_count(self):
        metadata = {
            **self.metadata,
            "selected_k": 2,
        }

        model = self.create_mock_model(
            [
                [0.0, 0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0, 2.0],
            ]
        )

        scaler = self.create_mock_scaler()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=self.segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=metadata,
        ):
            with self.assertRaises(
                UserSegmentProfileError
            ):
                get_user_segment_profile(
                    self.user_id
                )

    def test_missing_scaler_mean_is_rejected(self):
        model = self.create_mock_model(
            [
                [0.0, 0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0, 2.0],
            ]
        )

        scaler = type(
            "MockScaler",
            (),
            {
                "inverse_transform": lambda self, values: values,
            },
        )()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=self.segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ):
            with self.assertRaises(
                UserSegmentProfileError
            ):
                get_user_segment_profile(
                    self.user_id
                )

    def test_interpretation_failure_is_converted_to_profile_error(self):
        model = self.create_mock_model(
            [
                [0.0, 0.0, 0.0, 0.0],
                [1.0, 1.0, 1.0, 1.0],
                [2.0, 2.0, 2.0, 2.0],
            ]
        )

        scaler = self.create_mock_scaler()

        with patch(
            "ml.services.segmentation_profile."
            "predict_user_segment",
            return_value=self.segmentation_result,
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_model",
            return_value={
                "model": model,
                "scaler": scaler,
            },
        ), patch(
            "ml.services.segmentation_profile."
            "load_kmeans_metadata",
            return_value=self.metadata,
        ), patch(
            "ml.services.segmentation_profile."
            "interpret_cluster",
            side_effect=ValueError(
                "Invalid cluster interpretation."
            ),
        ):
            with self.assertRaises(
                UserSegmentProfileError
            ):
                get_user_segment_profile(
                    self.user_id
                )