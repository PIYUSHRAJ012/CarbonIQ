from datetime import date, datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

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
    get_segmentation_dataset,
    get_temporal_prediction_dataset,
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
    """
    Tests for Random Forest temporal prediction data generation
    and K-Means user-level segmentation data generation.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="mltest@example.com",
            full_name="ML Test User",
            password="TestPassword123!",
        )

        cls.second_user = CustomUser.objects.create_user(
            email="seconduser@example.com",
            full_name="Second User",
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

        cls.food_factor = EmissionFactor.objects.create(
            activity_category=cls.food,
            factor=Decimal("1.5000"),
            source="Test Source",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )

    def create_activity(
        self,
        user,
        created_at,
        electricity=0,
        transportation=0,
        food=0,
        total_emission=0,
        status=CarbonActivity.Status.COMPLETED,
    ):
        """
        Create a valid CarbonActivity with optional category quantities
        and a calculated footprint.
        """

        activity = CarbonActivity.objects.create(
            user=user,
            status=status,
        )

        # CarbonActivity.created_at uses auto_now_add, so set the
        # desired historical timestamp after creation.
        activity.created_at = timezone.make_aware(
            datetime(
                created_at.year,
                created_at.month,
                created_at.day,
                12,
                0,
                0,
            )
        )
        activity.save(update_fields=["created_at"])

        if electricity > 0:
            ActivityEntry.objects.create(
                carbon_activity=activity,
                category=self.electricity,
                emission_factor=self.electricity_factor,
                quantity=Decimal(str(electricity)),
                emission_factor_snapshot=Decimal("0.7000"),
                entry_emission=(
                    Decimal(str(electricity))
                    * Decimal("0.7000")
                ),
            )

        if transportation > 0:
            ActivityEntry.objects.create(
                carbon_activity=activity,
                category=self.transportation,
                emission_factor=self.transportation_factor,
                quantity=Decimal(str(transportation)),
                emission_factor_snapshot=Decimal("0.2000"),
                entry_emission=(
                    Decimal(str(transportation))
                    * Decimal("0.2000")
                ),
            )

        if food > 0:
            ActivityEntry.objects.create(
                carbon_activity=activity,
                category=self.food,
                emission_factor=self.food_factor,
                quantity=Decimal(str(food)),
                emission_factor_snapshot=Decimal("1.5000"),
                entry_emission=(
                    Decimal(str(food))
                    * Decimal("1.5000")
                ),
            )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal(str(total_emission)),
        )

        return activity

    # ================================================================
    # Random Forest temporal prediction dataset tests
    # ================================================================

    def test_temporal_dataset_creates_one_row_for_consecutive_months(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=200,
            transportation=80,
            total_emission=140,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertEqual(len(X), 1)
        self.assertEqual(len(y), 1)
        self.assertEqual(len(metadata), 1)

    def test_temporal_features_use_previous_month(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=200,
            transportation=80,
            total_emission=140,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertEqual(
            X.iloc[0]["previous_electricity"],
            100.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_transportation"],
            50.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_total_emission"],
            80.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_submission_count"],
            1,
        )

    def test_temporal_target_is_next_month_total_emission(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=200,
            total_emission=140,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertEqual(
            y.iloc[0],
            140.0,
        )

        self.assertEqual(
            y.name,
            "next_total_emission",
        )

    def test_multiple_submissions_in_previous_month_are_aggregated(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 5),
            electricity=100,
            transportation=20,
            total_emission=60,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 20),
            electricity=200,
            transportation=30,
            total_emission=90,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 10),
            electricity=250,
            total_emission=175,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertEqual(len(X), 1)

        self.assertEqual(
            X.iloc[0]["previous_electricity"],
            300.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_transportation"],
            50.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_total_emission"],
            150.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_submission_count"],
            2,
        )

    def test_missing_category_is_zero(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=70,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=150,
            total_emission=105,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertIn(
            "previous_food",
            X.columns,
        )

        self.assertEqual(
            X.iloc[0]["previous_food"],
            0.0,
        )

    def test_missing_month_does_not_create_two_month_transition(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=70,
        )

        # February intentionally has no completed activity.

        self.create_activity(
            user=self.user,
            created_at=date(2026, 3, 15),
            electricity=200,
            total_emission=140,
        )

        with self.assertRaises(MLDataError):
            get_temporal_prediction_dataset()

    def test_single_month_user_produces_no_training_pair(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=70,
        )

        with self.assertRaises(MLDataError):
            get_temporal_prediction_dataset()

    def test_failed_submission_is_excluded_from_temporal_dataset(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=70,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 20),
            electricity=9999,
            total_emission=6999.30,
            status=CarbonActivity.Status.FAILED,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=150,
            total_emission=105,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertEqual(len(X), 1)

        self.assertEqual(
            X.iloc[0]["previous_electricity"],
            100.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_total_emission"],
            70.0,
        )

        self.assertEqual(
            X.iloc[0]["previous_submission_count"],
            1,
        )

    def test_target_period_information_is_not_in_features(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=200,
            transportation=80,
            food=30,
            total_emission=185,
        )

        X, y, metadata = get_temporal_prediction_dataset()

        self.assertNotIn(
            "total_emission",
            X.columns,
        )

        self.assertNotIn(
            "food",
            X.columns,
        )

        self.assertNotIn(
            "next_total_emission",
            X.columns,
        )

        self.assertNotIn(
            "target_period",
            X.columns,
        )

        self.assertIn(
            "target_period",
            metadata.columns,
        )

    # ================================================================
    # K-Means segmentation dataset tests
    # ================================================================

    def test_segmentation_dataset_contains_one_row_per_user(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        X, metadata = get_segmentation_dataset()

        self.assertEqual(len(X), 1)
        self.assertEqual(len(metadata), 1)

        self.assertEqual(
            metadata.iloc[0]["user_id"],
            self.user.id,
        )

    def test_segmentation_aggregates_multiple_submissions(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 2, 15),
            electricity=200,
            total_emission=140,
        )

        X, metadata = get_segmentation_dataset()

        self.assertEqual(len(X), 1)

        self.assertEqual(
            X.iloc[0]["electricity"],
            150.0,
        )

        self.assertEqual(
            X.iloc[0]["submission_count"],
            2,
        )

        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            110.0,
        )

    def test_segmentation_missing_category_is_zero(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=70,
        )

        X, metadata = get_segmentation_dataset()

        self.assertIn(
            "food",
            X.columns,
        )

        self.assertEqual(
            X.iloc[0]["food"],
            0.0,
        )

    def test_segmentation_contains_average_total_emission(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=80,
        )

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
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=80,
        )

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
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=80,
        )

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
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 20),
            electricity=9999,
            total_emission=6999.30,
            status=CarbonActivity.Status.FAILED,
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

    def test_user_without_completed_activity_is_excluded(self):
        self.create_activity(
            user=self.user,
            created_at=date(2026, 1, 15),
            electricity=100,
            total_emission=80,
        )

        X, metadata = get_segmentation_dataset()

        user_ids = metadata["user_id"].tolist()

        self.assertIn(
            self.user.id,
            user_ids,
        )

        self.assertNotIn(
            self.second_user.id,
            user_ids,
        )