from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError

from ml.services.feature_engineering import MLDataError
from ml.services.model_persistence import ModelPersistenceError
from ml.training.kmeans import KMeansTrainingResult


class TrainUserSegmentsCommandTests(TestCase):
    """Tests for the train_user_segments management command."""

    def setUp(self):
        self.training_result = KMeansTrainingResult(
            model="mock-kmeans-model",
            scaler="mock-standard-scaler",
            feature_names=(
                "electricity",
                "transportation",
                "avg_total_emission",
                "submission_count",
            ),
            user_count=20,
            selected_k=3,
            candidate_scores={
                2: 0.51,
                3: 0.68,
                4: 0.57,
                5: 0.44,
            },
            silhouette_score=0.68,
            labels=None,
            cluster_sizes={
                0: 7,
                1: 6,
                2: 7,
            },
        )

    @patch(
        "ml.management.commands.train_user_segments."
        "save_kmeans_model"
    )
    @patch(
        "ml.management.commands.train_user_segments."
        "train_kmeans_from_database"
    )
    def test_command_trains_and_saves_model(
        self,
        mock_train,
        mock_save,
    ):
        mock_train.return_value = self.training_result

        mock_save.return_value = (
            Path("artifacts/ml/user_segmenter.joblib"),
            Path("artifacts/ml/user_segmenter_metadata.json"),
        )

        call_command(
            "train_user_segments"
        )

        mock_train.assert_called_once()
        mock_save.assert_called_once()

        _, kwargs = mock_save.call_args

        self.assertEqual(
            kwargs["model"],
            self.training_result.model,
        )

        self.assertEqual(
            kwargs["scaler"],
            self.training_result.scaler,
        )

        metadata = kwargs["metadata"]

        self.assertEqual(
            metadata["model_version"],
            "kmeans-v1",
        )

        self.assertEqual(
            metadata["model_type"],
            "user_segmentation",
        )

        self.assertEqual(
            metadata["features"],
            [
                "electricity",
                "transportation",
                "avg_total_emission",
                "submission_count",
            ],
        )

        self.assertEqual(
            metadata["user_count"],
            20,
        )

        self.assertEqual(
            metadata["selected_k"],
            3,
        )

        self.assertEqual(
            metadata["candidate_scores"],
            {
                "2": 0.51,
                "3": 0.68,
                "4": 0.57,
                "5": 0.44,
            },
        )

        self.assertEqual(
            metadata["silhouette_score"],
            0.68,
        )

        self.assertEqual(
            metadata["cluster_sizes"],
            {
                "0": 7,
                "1": 6,
                "2": 7,
            },
        )

    @patch(
        "ml.management.commands.train_user_segments."
        "train_kmeans_from_database"
    )
    def test_command_fails_when_user_data_is_insufficient(
        self,
        mock_train,
    ):
        mock_train.side_effect = MLDataError(
            "At least 10 users are required for K-Means segmentation."
        )

        with self.assertRaises(CommandError) as context:
            call_command(
                "train_user_segments"
            )

        self.assertIn(
            "At least 10 users are required for K-Means segmentation.",
            str(context.exception),
        )

        mock_train.assert_called_once()

    @patch(
        "ml.management.commands.train_user_segments."
        "train_kmeans_from_database"
    )
    def test_command_handles_persistence_failure(
        self,
        mock_train,
    ):
        mock_train.return_value = self.training_result

        with patch(
            "ml.management.commands.train_user_segments."
            "save_kmeans_model"
        ) as mock_save:
            mock_save.side_effect = ModelPersistenceError(
                "Failed to save K-Means artifacts."
            )

            with self.assertRaises(CommandError) as context:
                call_command(
                    "train_user_segments"
                )

        self.assertIn(
            "Failed to save K-Means artifacts.",
            str(context.exception),
        )

        mock_train.assert_called_once()
        mock_save.assert_called_once()

    @patch(
        "ml.management.commands.train_user_segments."
        "save_kmeans_model"
    )
    @patch(
        "ml.management.commands.train_user_segments."
        "train_kmeans_from_database"
    )
    def test_command_does_not_save_when_training_fails(
        self,
        mock_train,
        mock_save,
    ):
        mock_train.side_effect = MLDataError(
            "No completed CarbonIQ users are available."
        )

        with self.assertRaises(CommandError):
            call_command(
                "train_user_segments"
            )

        mock_train.assert_called_once()
        mock_save.assert_not_called()