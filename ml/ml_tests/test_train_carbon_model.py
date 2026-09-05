from pathlib import Path
from unittest import TestCase
from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError

from ml.services.feature_engineering import MLDataError
from ml.services.model_persistence import ModelPersistenceError
from ml.training.random_forest import RandomForestTrainingResult


class TrainCarbonModelCommandTests(TestCase):
    """Tests for the train_carbon_model management command."""

    def setUp(self):
        self.training_result = RandomForestTrainingResult(
            model="mock-random-forest",
            feature_names=(
                "previous_electricity",
                "previous_transportation",
                "previous_total_emission",
                "previous_submission_count",
            ),
            sample_count=40,
            training_samples=32,
            test_samples=8,
            user_count=5,
            training_period_start="2026-01",
            training_period_end="2026-04",
            test_period_start="2026-05",
            test_period_end="2026-06",
            mae=10.25,
            rmse=14.75,
            r2=0.85,
        )

    @patch(
        "ml.management.commands.train_carbon_model."
        "save_random_forest_model"
    )
    @patch(
        "ml.management.commands.train_carbon_model."
        "train_random_forest_from_database"
    )
    def test_command_trains_and_saves_model(
        self,
        mock_train,
        mock_save,
    ):
        mock_train.return_value = self.training_result

        mock_save.return_value = (
            Path("artifacts/ml/carbon_predictor.joblib"),
            Path("artifacts/ml/carbon_predictor_metadata.json"),
        )

        call_command("train_carbon_model")

        mock_train.assert_called_once()
        mock_save.assert_called_once()

        _, kwargs = mock_save.call_args

        metadata = kwargs["metadata"]

        self.assertEqual(
            metadata["model_version"],
            "rf-temporal-v1",
        )

        self.assertEqual(
            metadata["prediction_type"],
            "next_month_carbon_footprint",
        )

        self.assertEqual(
            metadata["target"],
            "next_total_emission",
        )

        self.assertEqual(
            metadata["features"],
            [
                "previous_electricity",
                "previous_transportation",
                "previous_total_emission",
                "previous_submission_count",
            ],
        )

        self.assertEqual(
            metadata["sample_count"],
            40,
        )

        self.assertEqual(
            metadata["training_samples"],
            32,
        )

        self.assertEqual(
            metadata["test_samples"],
            8,
        )

        self.assertEqual(
            metadata["user_count"],
            5,
        )

        self.assertEqual(
            metadata["training_period_start"],
            "2026-01",
        )

        self.assertEqual(
            metadata["training_period_end"],
            "2026-04",
        )

        self.assertEqual(
            metadata["test_period_start"],
            "2026-05",
        )

        self.assertEqual(
            metadata["test_period_end"],
            "2026-06",
        )

        self.assertEqual(
            metadata["mae"],
            10.25,
        )

        self.assertEqual(
            metadata["rmse"],
            14.75,
        )

        self.assertEqual(
            metadata["r2"],
            0.85,
        )

    @patch(
        "ml.management.commands.train_carbon_model."
        "train_random_forest_from_database"
    )
    def test_command_fails_when_training_data_is_insufficient(
        self,
        mock_train,
    ):
        mock_train.side_effect = MLDataError(
            "At least 30 temporal training transitions are required."
        )

        with self.assertRaises(CommandError) as context:
            call_command("train_carbon_model")

        self.assertIn(
            "At least 30 temporal training transitions are required.",
            str(context.exception),
        )

        mock_train.assert_called_once()

    @patch(
        "ml.management.commands.train_carbon_model."
        "train_random_forest_from_database"
    )
    def test_command_handles_persistence_failure(
        self,
        mock_train,
    ):
        mock_train.return_value = self.training_result

        with patch(
            "ml.management.commands.train_carbon_model."
            "save_random_forest_model"
        ) as mock_save:
            mock_save.side_effect = ModelPersistenceError(
                "Failed to save Random Forest artifacts."
            )

            with self.assertRaises(CommandError) as context:
                call_command("train_carbon_model")

        self.assertIn(
            "Failed to save Random Forest artifacts.",
            str(context.exception),
        )

        mock_train.assert_called_once()
        mock_save.assert_called_once()

    @patch(
        "ml.management.commands.train_carbon_model."
        "save_random_forest_model"
    )
    @patch(
        "ml.management.commands.train_carbon_model."
        "train_random_forest_from_database"
    )
    def test_command_does_not_save_when_training_fails(
        self,
        mock_train,
        mock_save,
    ):
        mock_train.side_effect = MLDataError(
            "No completed carbon activities are available."
        )

        with self.assertRaises(CommandError):
            call_command("train_carbon_model")

        mock_train.assert_called_once()
        mock_save.assert_not_called()