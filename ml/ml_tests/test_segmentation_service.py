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

from ml.services.feature_engineering import MLDataError
from ml.services.segmentation import get_user_segmentation_features


class UserSegmentationFeatureTests(TestCase):
    """Tests for single-user segmentation feature generation."""

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="segment_user@example.com",
            full_name="Segment User",
            password="TestPassword123!",
        )

        cls.other_user = CustomUser.objects.create_user(
            email="other_segment_user@example.com",
            full_name="Other Segment User",
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

    def create_activity(
        self,
        user,
        electricity=0,
        transportation=0,
        total_emission=0,
        status=CarbonActivity.Status.COMPLETED,
    ):
        """Create a valid CarbonActivity for segmentation tests."""

        activity = CarbonActivity.objects.create(
            user=user,
            status=status,
        )

        if electricity:
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

        if transportation:
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

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal(str(total_emission)),
        )

        return activity

    def test_returns_one_row_for_requested_user(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        self.create_activity(
            user=self.other_user,
            electricity=999,
            transportation=999,
            total_emission=999,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertEqual(
            len(X),
            1,
        )

        self.assertEqual(
            len(metadata),
            1,
        )

        self.assertEqual(
            metadata.iloc[0]["user_id"],
            self.user.id,
        )

    def test_category_quantities_are_aggregated(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            transportation=50,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            electricity=200,
            transportation=30,
            total_emission=140,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertEqual(
            X.iloc[0]["electricity"],
            300.0,
        )

        self.assertEqual(
            X.iloc[0]["transportation"],
            80.0,
        )

    def test_average_total_emission_is_correct(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            total_emission=80,
        )

        self.create_activity(
            user=self.user,
            electricity=200,
            total_emission=140,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            110.0,
        )

    def test_submission_count_is_correct(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            total_emission=70,
        )

        self.create_activity(
            user=self.user,
            electricity=150,
            total_emission=105,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertEqual(
            X.iloc[0]["submission_count"],
            2,
        )

    def test_missing_category_is_zero(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            total_emission=70,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertIn(
            "food",
            X.columns,
        )

        self.assertEqual(
            X.iloc[0]["food"],
            0.0,
        )

    def test_failed_submission_is_ignored(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            total_emission=70,
        )

        self.create_activity(
            user=self.user,
            electricity=9999,
            total_emission=6999.30,
            status=CarbonActivity.Status.FAILED,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertEqual(
            X.iloc[0]["electricity"],
            100.0,
        )

        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            70.0,
        )

        self.assertEqual(
            X.iloc[0]["submission_count"],
            1,
        )

    def test_user_id_is_not_a_feature(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            total_emission=70,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertNotIn(
            "user_id",
            X.columns,
        )

        self.assertIn(
            "user_id",
            metadata.columns,
        )

    def test_user_without_completed_activity_raises_error(self):
        with self.assertRaises(MLDataError):
            get_user_segmentation_features(
                self.user.id
            )

    def test_user_isolated_from_other_users(self):
        self.create_activity(
            user=self.user,
            electricity=100,
            total_emission=70,
        )

        self.create_activity(
            user=self.other_user,
            electricity=999,
            total_emission=699,
        )

        X, metadata = get_user_segmentation_features(
            self.user.id
        )

        self.assertEqual(
            X.iloc[0]["electricity"],
            100.0,
        )

        self.assertEqual(
            X.iloc[0]["avg_total_emission"],
            70.0,
        )