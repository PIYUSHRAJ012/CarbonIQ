from unittest import TestCase

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

from ml.services.feature_engineering import MLDataError
from ml.training.kmeans import (
    MAX_K,
    MIN_K,
    MINIMUM_USERS,
    N_INIT,
    RANDOM_STATE,
    evaluate_k_values,
    train_kmeans,
    validate_segmentation_data,
)


class KMeansValidationTests(TestCase):
    """Tests for K-Means segmentation-data validation."""

    def create_valid_dataset(self, user_count=10):
        X = pd.DataFrame(
            {
                "electricity": np.arange(
                    user_count,
                    dtype=float,
                ),
                "transportation": np.arange(
                    user_count,
                    dtype=float,
                ) * 2,
                "avg_total_emission": np.arange(
                    user_count,
                    dtype=float,
                ) * 3,
                "submission_count": np.ones(
                    user_count,
                    dtype=float,
                ),
            }
        )

        metadata = pd.DataFrame(
            {
                "user_id": range(
                    1,
                    user_count + 1,
                )
            }
        )

        return X, metadata

    def test_empty_dataset_is_rejected(self):
        X = pd.DataFrame()
        metadata = pd.DataFrame()

        with self.assertRaises(MLDataError):
            validate_segmentation_data(
                X,
                metadata,
            )

    def test_mismatched_lengths_are_rejected(self):
        X, metadata = self.create_valid_dataset()

        metadata = metadata.iloc[:-1]

        with self.assertRaises(MLDataError):
            validate_segmentation_data(
                X,
                metadata,
            )

    def test_insufficient_users_are_rejected(self):
        X, metadata = self.create_valid_dataset(
            user_count=MINIMUM_USERS - 1,
        )

        with self.assertRaises(MLDataError):
            validate_segmentation_data(
                X,
                metadata,
            )

    def test_missing_feature_values_are_rejected(self):
        X, metadata = self.create_valid_dataset()

        X.loc[0, "electricity"] = np.nan

        with self.assertRaises(MLDataError):
            validate_segmentation_data(
                X,
                metadata,
            )

    def test_user_id_must_exist_in_metadata(self):
        X, metadata = self.create_valid_dataset()

        metadata = metadata.rename(
            columns={
                "user_id": "id",
            }
        )

        with self.assertRaises(MLDataError):
            validate_segmentation_data(
                X,
                metadata,
            )

    def test_user_id_is_not_allowed_in_features(self):
        X, metadata = self.create_valid_dataset()

        X["user_id"] = metadata["user_id"]

        with self.assertRaises(MLDataError):
            validate_segmentation_data(
                X,
                metadata,
            )

    def test_valid_segmentation_data_is_accepted(self):
        X, metadata = self.create_valid_dataset()

        validate_segmentation_data(
            X,
            metadata,
        )


class KMeansEvaluationTests(TestCase):
    """Tests for candidate K evaluation."""

    def create_clustered_dataset(self):
        X = pd.DataFrame(
            {
                "electricity": [
                    10,
                    12,
                    11,
                    100,
                    105,
                    110,
                    200,
                    205,
                    210,
                    215,
                ],
                "transportation": [
                    10,
                    11,
                    12,
                    100,
                    105,
                    110,
                    200,
                    205,
                    210,
                    215,
                ],
                "avg_total_emission": [
                    20,
                    22,
                    21,
                    200,
                    210,
                    220,
                    400,
                    410,
                    420,
                    430,
                ],
                "submission_count": [
                    2,
                    2,
                    2,
                    3,
                    3,
                    3,
                    4,
                    4,
                    4,
                    4,
                ],
            }
        )

        return X

    def test_candidate_scores_are_returned_for_valid_k_values(self):
        X = self.create_clustered_dataset()

        scores = evaluate_k_values(
            X,
            min_k=MIN_K,
            max_k=MAX_K,
        )

        self.assertIsInstance(
            scores,
            dict,
        )

        self.assertGreaterEqual(
            len(scores),
            1,
        )

        for k, score in scores.items():
            self.assertGreaterEqual(
                k,
                MIN_K,
            )

            self.assertLessEqual(
                k,
                MAX_K,
            )

            self.assertTrue(
                np.isfinite(score)
            )

    def test_invalid_k_range_is_rejected(self):
        X = self.create_clustered_dataset()

        with self.assertRaises(MLDataError):
            evaluate_k_values(
                X,
                min_k=1,
                max_k=1,
            )

    def test_k_values_are_bounded_by_user_count(self):
        X = self.create_clustered_dataset()

        scores = evaluate_k_values(
            X,
            min_k=2,
            max_k=len(X) + 1,
        )

        self.assertTrue(scores)

        for k in scores:
            self.assertLess(
                k,
                len(X),
            )


class KMeansTrainingTests(TestCase):
    """Tests for final K-Means model training."""

    def create_clustered_dataset(self, user_count=15):
        rng = np.random.default_rng(42)

        group_one = np.column_stack(
            [
                rng.normal(10, 1, 5),
                rng.normal(10, 1, 5),
                rng.normal(20, 2, 5),
                np.full(5, 2),
            ]
        )

        group_two = np.column_stack(
            [
                rng.normal(100, 2, 5),
                rng.normal(100, 2, 5),
                rng.normal(200, 5, 5),
                np.full(5, 3),
            ]
        )

        group_three = np.column_stack(
            [
                rng.normal(200, 2, 5),
                rng.normal(200, 2, 5),
                rng.normal(400, 5, 5),
                np.full(5, 4),
            ]
        )

        values = np.vstack(
            [
                group_one,
                group_two,
                group_three,
            ]
        )

        X = pd.DataFrame(
            values,
            columns=[
                "electricity",
                "transportation",
                "avg_total_emission",
                "submission_count",
            ],
        )

        metadata = pd.DataFrame(
            {
                "user_id": range(
                    1,
                    len(X) + 1,
                )
            }
        )

        return X, metadata

    def test_training_returns_kmeans_model(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertIsInstance(
            result.model,
            KMeans,
        )

    def test_training_returns_standard_scaler(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertIsInstance(
            result.scaler,
            StandardScaler,
        )

    def test_feature_names_are_preserved(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertEqual(
            result.feature_names,
            tuple(X.columns),
        )

    def test_user_count_is_correct(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertEqual(
            result.user_count,
            len(X),
        )

    def test_selected_k_is_valid(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertGreaterEqual(
            result.selected_k,
            MIN_K,
        )

        self.assertLessEqual(
            result.selected_k,
            MAX_K,
        )

    def test_cluster_labels_are_generated_for_every_user(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        labels = result.labels

        self.assertEqual(
            len(labels),
            len(X),
        )

    def test_cluster_count_matches_selected_k(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        unique_labels = np.unique(
            result.labels
        )

        self.assertLessEqual(
            len(unique_labels),
            result.selected_k,
        )

    def test_silhouette_score_is_finite(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertTrue(
            np.isfinite(
                result.silhouette_score
            )
        )

    def test_cluster_sizes_sum_to_user_count(self):
        X, metadata = self.create_clustered_dataset()

        result = train_kmeans(
            X,
            metadata,
        )

        self.assertEqual(
            sum(result.cluster_sizes.values()),
            result.user_count,
        )

    def test_training_is_reproducible(self):
        X, metadata = self.create_clustered_dataset()

        first_result = train_kmeans(
            X,
            metadata,
        )

        second_result = train_kmeans(
            X,
            metadata,
        )

        self.assertEqual(
            first_result.selected_k,
            second_result.selected_k,
        )

        self.assertEqual(
            first_result.silhouette_score,
            second_result.silhouette_score,
        )

        np.testing.assert_array_equal(
            first_result.labels,
            second_result.labels,
        )


class KMeansConfigurationTests(TestCase):
    """Tests for K-Means configuration."""

    def test_minimum_k_is_two(self):
        self.assertEqual(
            MIN_K,
            2,
        )

    def test_maximum_k_is_five(self):
        self.assertEqual(
            MAX_K,
            5,
        )

    def test_minimum_users_is_ten(self):
        self.assertEqual(
            MINIMUM_USERS,
            10,
        )

    def test_random_state_is_reproducible(self):
        self.assertEqual(
            RANDOM_STATE,
            42,
        )

    def test_n_init_is_explicit(self):
        self.assertEqual(
            N_INIT,
            20,
        )