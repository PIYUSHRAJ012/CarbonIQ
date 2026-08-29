from unittest import TestCase

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestRegressor

from ml.services.feature_engineering import MLDataError
from ml.training.random_forest import (
    MINIMUM_SAMPLES,
    TEST_SIZE,
    train_random_forest,
    validate_training_data,
)


class RandomForestValidationTests(TestCase):
    """Tests for Random Forest training-data validation."""

    def create_valid_dataset(self, sample_count=30):
        X = pd.DataFrame(
            {
                "electricity": np.arange(sample_count, dtype=float),
                "transportation": np.arange(sample_count, dtype=float) * 2,
                "food": np.arange(sample_count, dtype=float) * 0.5,
            }
        )

        y = pd.Series(
            np.arange(sample_count, dtype=float) * 3,
            name="total_emission",
        )

        return X, y

    def test_empty_features_are_rejected(self):
        X = pd.DataFrame()
        y = pd.Series(dtype=float)

        with self.assertRaises(MLDataError):
            validate_training_data(X, y)

    def test_mismatched_feature_and_target_lengths_are_rejected(self):
        X, y = self.create_valid_dataset()

        y = y.iloc[:-1]

        with self.assertRaises(MLDataError):
            validate_training_data(X, y)

    def test_insufficient_samples_are_rejected(self):
        X, y = self.create_valid_dataset(
            sample_count=MINIMUM_SAMPLES - 1
        )

        with self.assertRaises(MLDataError):
            validate_training_data(X, y)

    def test_missing_feature_values_are_rejected(self):
        X, y = self.create_valid_dataset()

        X.loc[0, "electricity"] = np.nan

        with self.assertRaises(MLDataError):
            validate_training_data(X, y)

    def test_missing_target_values_are_rejected(self):
        X, y = self.create_valid_dataset()

        y.iloc[0] = np.nan

        with self.assertRaises(MLDataError):
            validate_training_data(X, y)

    def test_valid_training_data_is_accepted(self):
        X, y = self.create_valid_dataset()

        validate_training_data(X, y)


class RandomForestTrainingTests(TestCase):
    """Tests for Random Forest training."""

    def create_valid_dataset(self, sample_count=40):
        rng = np.random.default_rng(42)

        electricity = rng.uniform(10, 300, sample_count)
        transportation = rng.uniform(10, 500, sample_count)
        food = rng.uniform(1, 50, sample_count)

        total_emission = (
            electricity * 0.7
            + transportation * 0.2
            + food * 1.5
        )

        X = pd.DataFrame(
            {
                "electricity": electricity,
                "transportation": transportation,
                "food": food,
            }
        )

        y = pd.Series(
            total_emission,
            name="total_emission",
        )

        return X, y

    def test_training_returns_random_forest_model(self):
        X, y = self.create_valid_dataset()

        result = train_random_forest(X, y)

        self.assertIsInstance(
            result.model,
            RandomForestRegressor,
        )

    def test_training_preserves_feature_names(self):
        X, y = self.create_valid_dataset()

        result = train_random_forest(X, y)

        self.assertEqual(
            result.feature_names,
            tuple(X.columns),
        )

    def test_training_sample_count_is_correct(self):
        X, y = self.create_valid_dataset(
            sample_count=40
        )

        result = train_random_forest(X, y)

        self.assertEqual(
            result.sample_count,
            40,
        )

    def test_train_test_split_sizes_are_correct(self):
        X, y = self.create_valid_dataset(
            sample_count=40
        )

        result = train_random_forest(X, y)

        expected_test_samples = 8
        expected_training_samples = 32

        self.assertEqual(
            result.test_samples,
            expected_test_samples,
        )

        self.assertEqual(
            result.training_samples,
            expected_training_samples,
        )

    def test_training_metrics_are_finite(self):
        X, y = self.create_valid_dataset()

        result = train_random_forest(X, y)

        self.assertTrue(
            np.isfinite(result.mae)
        )

        self.assertTrue(
            np.isfinite(result.rmse)
        )

        self.assertTrue(
            np.isfinite(result.r2)
        )

    def test_rmse_is_not_less_than_mae(self):
        X, y = self.create_valid_dataset()

        result = train_random_forest(X, y)

        self.assertGreaterEqual(
            result.rmse,
            result.mae,
        )

    def test_training_is_reproducible(self):
        X, y = self.create_valid_dataset()

        first_result = train_random_forest(X, y)
        second_result = train_random_forest(X, y)

        self.assertEqual(
            first_result.mae,
            second_result.mae,
        )

        self.assertEqual(
            first_result.rmse,
            second_result.rmse,
        )

        self.assertEqual(
            first_result.r2,
            second_result.r2,
        )

    def test_default_test_size_is_20_percent(self):
        self.assertEqual(
            TEST_SIZE,
            0.20,
        )