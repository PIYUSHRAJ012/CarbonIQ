from datetime import date

import numpy as np
import pandas as pd
from django.test import SimpleTestCase
from sklearn.ensemble import RandomForestRegressor

from ml.services.feature_engineering import MLDataError
from ml.training.random_forest import (
    MINIMUM_TRANSITIONS,
    MINIMUM_USERS,
    N_ESTIMATORS,
    RANDOM_STATE,
    TEST_SIZE,
    chronological_train_test_split,
    train_random_forest,
    validate_training_data,
)


class RandomForestValidationTests(SimpleTestCase):
    """Tests for temporal Random Forest training-data validation."""

    def create_valid_dataset(
        self,
        sample_count=30,
        user_count=5,
        period_count=6,
    ):
        users = [
            index % user_count + 1
            for index in range(sample_count)
        ]

        target_periods = pd.period_range(
            start="2026-02",
            periods=period_count,
            freq="M",
        )

        repeated_periods = [
            target_periods[index % period_count]
            for index in range(sample_count)
        ]

        metadata = pd.DataFrame(
            {
                "user_id": users,
                "feature_period": [
                    period - 1
                    for period in repeated_periods
                ],
                "target_period": repeated_periods,
            }
        )

        X = pd.DataFrame(
            {
                "previous_electricity": np.arange(
                    sample_count,
                    dtype=float,
                ),
                "previous_transportation": (
                    np.arange(
                        sample_count,
                        dtype=float,
                    )
                    * 2
                ),
                "previous_total_emission": (
                    np.arange(
                        sample_count,
                        dtype=float,
                    )
                    * 3
                ),
                "previous_submission_count": np.ones(
                    sample_count,
                    dtype=float,
                ),
            }
        )

        y = pd.Series(
            np.arange(
                sample_count,
                dtype=float,
            )
            * 4,
            name="next_total_emission",
        )

        return X, y, metadata

    def test_empty_dataset_is_rejected(self):
        X = pd.DataFrame()
        y = pd.Series(dtype=float)
        metadata = pd.DataFrame()

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_mismatched_lengths_are_rejected(self):
        X, y, metadata = self.create_valid_dataset()

        y = y.iloc[:-1]

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_insufficient_transitions_are_rejected(self):
        X, y, metadata = self.create_valid_dataset(
            sample_count=MINIMUM_TRANSITIONS - 1,
        )

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_insufficient_users_are_rejected(self):
        X, y, metadata = self.create_valid_dataset(
            sample_count=30,
            user_count=MINIMUM_USERS - 1,
        )

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_missing_feature_values_are_rejected(self):
        X, y, metadata = self.create_valid_dataset()

        X.loc[0, "previous_electricity"] = np.nan

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_missing_target_values_are_rejected(self):
        X, y, metadata = self.create_valid_dataset()

        y.iloc[0] = np.nan

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_invalid_period_order_is_rejected(self):
        X, y, metadata = self.create_valid_dataset()

        metadata.loc[
            0,
            "target_period",
        ] = metadata.loc[
            0,
            "feature_period",
        ]

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_single_target_period_is_rejected(self):
        X, y, metadata = self.create_valid_dataset(
            period_count=1,
        )

        with self.assertRaises(MLDataError):
            validate_training_data(
                X,
                y,
                metadata,
            )

    def test_valid_training_data_is_accepted(self):
        X, y, metadata = self.create_valid_dataset()

        validate_training_data(
            X,
            y,
            metadata,
        )


class RandomForestSplitTests(SimpleTestCase):
    """Tests for chronological train/test splitting."""

    def create_valid_dataset(self):
        X = pd.DataFrame(
            {
                "previous_electricity": np.arange(
                    30,
                    dtype=float,
                ),
                "previous_transportation": np.arange(
                    30,
                    dtype=float,
                ),
            }
        )

        y = pd.Series(
            np.arange(30, dtype=float),
            name="next_total_emission",
        )

        target_periods = []

        for month in range(2, 8):
            target_period = pd.Period(
                f"2026-{month:02d}",
                freq="M",
            )

            target_periods.extend(
                [target_period] * 5
            )

        metadata = pd.DataFrame(
            {
                "user_id": [
                    index % 5 + 1
                    for index in range(30)
                ],
                "feature_period": [
                    period - 1
                    for period in target_periods
                ],
                "target_period": target_periods,
            }
        )

        return X, y, metadata

    def test_latest_period_is_reserved_for_testing(self):
        X, y, metadata = self.create_valid_dataset()

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

        self.assertLess(
            metadata_train["target_period"].max(),
            metadata_test["target_period"].min(),
        )

    def test_training_and_test_sets_do_not_share_target_periods(self):
        X, y, metadata = self.create_valid_dataset()

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

        train_periods = set(
            metadata_train["target_period"]
        )

        test_periods = set(
            metadata_test["target_period"]
        )

        self.assertTrue(
            train_periods.isdisjoint(
                test_periods
            )
        )

    def test_split_contains_both_training_and_test_data(self):
        X, y, metadata = self.create_valid_dataset()

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

        self.assertGreater(
            len(X_train),
            0,
        )

        self.assertGreater(
            len(X_test),
            0,
        )

        self.assertGreater(
            len(y_train),
            0,
        )

        self.assertGreater(
            len(y_test),
            0,
        )


class RandomForestTrainingTests(SimpleTestCase):
    """Tests for temporal Random Forest model training."""

    def create_valid_dataset(self, sample_count=40):
        rng = np.random.default_rng(42)

        electricity = rng.uniform(
            10,
            300,
            sample_count,
        )

        transportation = rng.uniform(
            10,
            500,
            sample_count,
        )

        previous_total = (
            electricity * 0.5
            + transportation * 0.1
        )

        next_total_emission = (
            electricity * 0.4
            + transportation * 0.15
            + previous_total * 0.2
        )

        target_periods = pd.period_range(
            start="2026-02",
            periods=8,
            freq="M",
        )

        metadata = pd.DataFrame(
            {
                "user_id": [
                    index % 5 + 1
                    for index in range(sample_count)
                ],
                "feature_period": [
                    target_periods[
                        index % len(target_periods)
                    ] - 1
                    for index in range(sample_count)
                ],
                "target_period": [
                    target_periods[
                        index % len(target_periods)
                    ]
                    for index in range(sample_count)
                ],
            }
        )

        X = pd.DataFrame(
            {
                "previous_electricity": electricity,
                "previous_transportation": transportation,
                "previous_total_emission": previous_total,
                "previous_submission_count": np.ones(
                    sample_count,
                    dtype=float,
                ),
            }
        )

        y = pd.Series(
            next_total_emission,
            name="next_total_emission",
        )

        return X, y, metadata

    def test_training_returns_random_forest_model(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertIsInstance(
            result.model,
            RandomForestRegressor,
        )

    def test_training_preserves_feature_names(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertEqual(
            result.feature_names,
            tuple(X.columns),
        )

    def test_training_sample_count_is_correct(self):
        X, y, metadata = self.create_valid_dataset(
            sample_count=40,
        )

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertEqual(
            result.sample_count,
            40,
        )

    def test_user_count_is_correct(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertEqual(
            result.user_count,
            5,
        )

    def test_training_and_test_samples_are_nonzero(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertGreater(
            result.training_samples,
            0,
        )

        self.assertGreater(
            result.test_samples,
            0,
        )

    def test_training_metrics_are_finite(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

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
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertGreaterEqual(
            result.rmse,
            result.mae,
        )

    def test_training_is_reproducible(self):
        X, y, metadata = self.create_valid_dataset()

        first_result = train_random_forest(
            X,
            y,
            metadata,
        )

        second_result = train_random_forest(
            X,
            y,
            metadata,
        )

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

    def test_training_periods_are_recorded(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertIsNotNone(
            result.training_period_start
        )

        self.assertIsNotNone(
            result.training_period_end
        )

        self.assertIsNotNone(
            result.test_period_start
        )

        self.assertIsNotNone(
            result.test_period_end
        )

    def test_model_uses_expected_configuration(self):
        X, y, metadata = self.create_valid_dataset()

        result = train_random_forest(
            X,
            y,
            metadata,
        )

        self.assertEqual(
            result.model.n_estimators,
            N_ESTIMATORS,
        )

        self.assertEqual(
            result.model.random_state,
            RANDOM_STATE,
        )


class RandomForestConfigurationTests(SimpleTestCase):
    """Tests for Random Forest training configuration."""

    def test_default_test_size(self):
        self.assertEqual(
            TEST_SIZE,
            0.20,
        )

    def test_minimum_transition_count(self):
        self.assertEqual(
            MINIMUM_TRANSITIONS,
            30,
        )

    def test_minimum_user_count(self):
        self.assertEqual(
            MINIMUM_USERS,
            5,
        )