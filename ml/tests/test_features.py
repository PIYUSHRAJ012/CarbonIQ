from datetime import date
from decimal import Decimal

from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
)

from ml.services.feature_engineering import (
    MLDataError,
    get_prediction_dataset,
    get_segmentation_dataset,
    normalize_feature_name,
)


class NormalizeFeatureNameTests(TestCase):
    """Tests for ML feature-name normalization."""

    def test_simple_category(self):
        self.assertEqual(
            normalize_feature_name("Electricity"),
            "electricity",
        )

    def test_category_with_spaces_and_symbols(self):
        self.assertEqual(
            normalize_feature_name("Rice & Grain"),
            "rice_grain",
        )

    def test_category_with_extra_whitespace(self):
        self.assertEqual(
            normalize_feature_name("  Transportation  "),
            "transportation",
        )

    def test_empty_category_name_raises_error(self):
        with self.assertRaises(MLDataError):
            normalize_feature_name("   ")


class PredictionDatasetTests(TestCase):
    """Tests for Random Forest dataset generation."""

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="mltest@example.com",
            full_name="ML Test User",
            password="TestPassword123!",
        )

        cls.electricity = ActivityCategory.objects.create(
            name="Electricity",
            unit="kWh",
            is_active=True,
            display_order=1,
        )

        cls.transportation = ActivityCategory.objects.create(
            name="Transportation",
            unit="km",
            is_active=True,
            display_order=2,
        )

        cls.food = ActivityCategory.objects.create(
            name="Food",
            unit="meals",
            is_active=True,
            display_order=3,
        )

        # Test-only emission factors.
        # These are intentionally simple values and are NOT official
        # CarbonIQ emission factors.
        cls.electricity_factor = EmissionFactor.objects.create(
            activity_category=cls.electricity,
            factor=Decimal("0.7000"),
            source="Test Source",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )

        cls.transportation_factor = EmissionFactor.objects.create(
            activity_category=cls.transportation,
            factor=Decimal("0.2000"),
            source="Test Source",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )

    def create_completed_activity(self):
        """Create a valid completed activity with a calculated footprint."""

        activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("100.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("70.00"),
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.transportation,
            emission_factor=self.transportation_factor,
            quantity=Decimal("50.00"),
            emission_factor_snapshot=Decimal("0.2000"),
            entry_emission=Decimal("10.00"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("80.00"),
        )

        return activity

    def test_completed_activity_is_included(self):
        activity = self.create_completed_activity()

        X, y, metadata = get_prediction_dataset()

        self.assertEqual(len(X), 1)
        self.assertEqual(len(y), 1)
        self.assertEqual(len(metadata), 1)

        self.assertEqual(
            metadata.iloc[0]["activity_id"],
            activity.id,
        )

    def test_category_quantities_become_features(self):
        self.create_completed_activity()

        X, y, metadata = get_prediction_dataset()

        self.assertIn("electricity", X.columns)
        self.assertIn("transportation", X.columns)

        self.assertEqual(
            X.iloc[0]["electricity"],
            100.0,
        )

        self.assertEqual(
            X.iloc[0]["transportation"],
            50.0,
        )

    def test_multiple_entries_of_same_category_are_combined(self):
        activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("100.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("70.00"),
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("50.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("35.00"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("105.00"),
        )

        X, y, metadata = get_prediction_dataset()

        self.assertIn("electricity", X.columns)

        self.assertEqual(
            X.iloc[0]["electricity"],
            150.0,
        )

    def test_missing_category_is_filled_with_zero(self):
        self.create_completed_activity()

        X, y, metadata = get_prediction_dataset()

        self.assertIn("food", X.columns)

        self.assertEqual(
            X.iloc[0]["food"],
            0.0,
        )

    def test_target_is_total_emission(self):
        self.create_completed_activity()

        X, y, metadata = get_prediction_dataset()

        self.assertEqual(
            y.iloc[0],
            80.0,
        )

        self.assertEqual(
            y.name,
            "total_emission",
        )

    def test_target_and_calculated_emissions_are_not_features(self):
        self.create_completed_activity()

        X, y, metadata = get_prediction_dataset()

        self.assertNotIn("total_emission", X.columns)
        self.assertNotIn("entry_emission", X.columns)

    def test_failed_activity_is_excluded(self):
        CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.FAILED,
        )

        with self.assertRaises(MLDataError):
            get_prediction_dataset()

    def test_activity_without_footprint_is_excluded(self):
        CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        with self.assertRaises(MLDataError):
            get_prediction_dataset()

    def test_no_valid_data_raises_error(self):
        with self.assertRaises(MLDataError):
            get_prediction_dataset()

    def test_segmentation_dataset_contains_one_row_per_user(self):
        self.create_completed_activity()

        X, metadata = get_segmentation_dataset()

        self.assertEqual(len(X), 1)
        self.assertEqual(len(metadata), 1)

        self.assertEqual(
            metadata.iloc[0]["user_id"],
            self.user.id,
        )

    def test_segmentation_aggregates_multiple_submissions(self):
        self.create_completed_activity()

        second_activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=second_activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("200.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("140.00"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=second_activity,
            total_emission=Decimal("140.00"),
        )

        X, metadata = get_segmentation_dataset()

        self.assertEqual(len(X), 1)

        # Average electricity:
        # (100 + 200) / 2 = 150
        self.assertEqual(
            X.iloc[0]["electricity"],
            150.0,
        )

        self.assertEqual(
            X.iloc[0]["submission_count"],
            2,
        )

        # Average total emission:
        # (80 + 140) / 2 = 110
        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            110.0,
        )

    def test_segmentation_missing_category_is_zero(self):
        self.create_completed_activity()

        X, metadata = get_segmentation_dataset()

        self.assertIn("food", X.columns)

        self.assertEqual(
            X.iloc[0]["food"],
            0.0,
        )

    def test_segmentation_contains_average_total_emission(self):
        self.create_completed_activity()

        X, metadata = get_segmentation_dataset()

        self.assertIn(
            "avg_total_emission",
            X.columns,
        )

        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            80.0,
        )

    def test_segmentation_contains_submission_count(self):
        self.create_completed_activity()

        X, metadata = get_segmentation_dataset()

        self.assertIn(
            "submission_count",
            X.columns,
        )

        self.assertEqual(
            X.iloc[0]["submission_count"],
            1,
        )

    def test_user_id_is_not_a_clustering_feature(self):
        self.create_completed_activity()

        X, metadata = get_segmentation_dataset()

        self.assertNotIn(
            "user_id",
            X.columns,
        )

        self.assertIn(
            "user_id",
            metadata.columns,
        )

    def test_failed_submission_is_excluded_from_segmentation(self):
        self.create_completed_activity()

        failed_activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.FAILED,
        )

        # Deliberately give the failed submission a large value.
        # It must not affect the user's segmentation features.
        ActivityEntry.objects.create(
            carbon_activity=failed_activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("9999.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("6999.30"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=failed_activity,
            total_emission=Decimal("6999.30"),
        )

        X, metadata = get_segmentation_dataset()

        self.assertEqual(
            X.iloc[0]["electricity"],
            100.0,
        )

        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            80.0,
        )

        self.assertEqual(
            X.iloc[0]["submission_count"],
            1,
        )

    def test_segmentation_user_without_completed_activity_is_excluded(self):
        second_user = CustomUser.objects.create_user(
            email="noactivity@example.com",
            full_name="No Activity User",
            password="TestPassword123!",
        )

        # No completed activities for second_user.
        self.create_completed_activity()

        X, metadata = get_segmentation_dataset()

        user_ids = metadata["user_id"].tolist()

        self.assertIn(self.user.id, user_ids)
        self.assertNotIn(second_user.id, user_ids)