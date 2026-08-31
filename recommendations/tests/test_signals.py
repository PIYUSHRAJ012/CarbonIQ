from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
)

from ml.services.segmentation_profile import UserSegmentProfileError

from recommendations.services.signals import (
    RecommendationSignalError,
    build_recommendation_signals,
)


class RecommendationSignalServiceTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="signals@example.com",
            full_name="Signals Test User",
            password="TestPassword123!",
        )

        cls.other_user = CustomUser.objects.create_user(
            email="other-signals@example.com",
            full_name="Other Signals User",
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

    def create_completed_activity(
        self,
        user,
        electricity_quantity="100.00",
        transportation_quantity="50.00",
        total_emission="80.00",
    ):
        activity = CarbonActivity.objects.create(
            user=user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal(electricity_quantity),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal(electricity_quantity) * Decimal("0.7000"),
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.transportation,
            emission_factor=self.transportation_factor,
            quantity=Decimal(transportation_quantity),
            emission_factor_snapshot=Decimal("0.2000"),
            entry_emission=Decimal(transportation_quantity) * Decimal("0.2000"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal(total_emission),
        )

        return activity

    def create_failed_activity(self, user):
        activity = CarbonActivity.objects.create(
            user=user,
            status=CarbonActivity.Status.FAILED,
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.transportation,
            emission_factor=self.transportation_factor,
            quantity=Decimal("999.00"),
            emission_factor_snapshot=Decimal("0.2000"),
            entry_emission=Decimal("199.80"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("199.80"),
        )

        return activity

    @staticmethod
    def mock_segment_profile():
        return type(
            "MockUserSegmentProfile",
            (),
            {
                "profile_name": "Energy-oriented",
                "dominant_domain": "energy",
                "domain_scores": {
                    "energy": 2.0,
                    "transport": 1.0,
                    "food": 1.0,
                    "shopping": 1.0,
                    "waste": 1.0,
                },
                "feature_strengths": {
                    "electricity": 2.0,
                },
                "model_version": "kmeans-v1",
                "selected_k": 3,
            },
        )()

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_builds_analytics_signals(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(self.user)

        mock_segment_profile.side_effect = UserSegmentProfileError(
            "K-Means model unavailable."
        )

        signals = build_recommendation_signals(self.user)

        self.assertEqual(
            signals.total_emission,
            Decimal("80.0000"),
        )

        self.assertEqual(
            signals.top_category,
            "Electricity",
        )

        self.assertEqual(
            signals.top_category_emission,
            Decimal("70.0000"),
        )

        self.assertEqual(
            len(signals.category_emissions),
            2,
        )

        self.assertEqual(
            signals.rf_prediction,
            None,
        )

        self.assertEqual(
            signals.user_segment,
            None,
        )

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_failed_submissions_are_excluded(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(self.user)
        self.create_failed_activity(self.user)

        mock_segment_profile.side_effect = UserSegmentProfileError(
            "K-Means model unavailable."
        )

        signals = build_recommendation_signals(self.user)

        self.assertEqual(
            signals.total_emission,
            Decimal("80.0000"),
        )

        self.assertEqual(
            signals.top_category_emission,
            Decimal("70.0000"),
        )

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_user_isolation(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(
            self.user,
            electricity_quantity="100.00",
            transportation_quantity="50.00",
            total_emission="80.00",
        )

        self.create_completed_activity(
            self.other_user,
            electricity_quantity="500.00",
            transportation_quantity="1000.00",
            total_emission="550.00",
        )

        mock_segment_profile.side_effect = UserSegmentProfileError(
            "K-Means model unavailable."
        )

        signals = build_recommendation_signals(self.user)

        self.assertEqual(
            signals.total_emission,
            Decimal("80.0000"),
        )

        self.assertEqual(
            signals.top_category_emission,
            Decimal("70.0000"),
        )

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_kmeans_profile_is_included(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(self.user)

        mock_segment_profile.return_value = (
            self.mock_segment_profile()
        )

        signals = build_recommendation_signals(self.user)

        self.assertEqual(
            signals.user_segment,
            "Energy-oriented",
        )

        self.assertEqual(
            signals.dominant_domain,
            "energy",
        )

        self.assertEqual(
            signals.segment_domain_scores["energy"],
            2.0,
        )

        self.assertEqual(
            signals.segment_feature_strengths["electricity"],
            2.0,
        )

        self.assertEqual(
            signals.segment_model_version,
            "kmeans-v1",
        )

        self.assertEqual(
            signals.segment_selected_k,
            3,
        )

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_kmeans_unavailability_is_non_fatal(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(self.user)

        mock_segment_profile.side_effect = UserSegmentProfileError(
            "No trained K-Means model is available."
        )

        signals = build_recommendation_signals(self.user)

        self.assertIsNone(signals.user_segment)
        self.assertIsNone(signals.dominant_domain)
        self.assertIsNone(signals.segment_domain_scores)
        self.assertIsNone(signals.segment_feature_strengths)
        self.assertIsNone(signals.segment_model_version)
        self.assertIsNone(signals.segment_selected_k)

        self.assertEqual(
            signals.total_emission,
            Decimal("80.0000"),
        )

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_empty_user_data_returns_zero_signals(
        self,
        mock_segment_profile,
    ):
        mock_segment_profile.side_effect = UserSegmentProfileError(
            "No trained K-Means model is available."
        )

        signals = build_recommendation_signals(self.user)

        self.assertEqual(
            signals.total_emission,
            Decimal("0.0000"),
        )

        self.assertIsNone(
            signals.top_category,
        )

        self.assertEqual(
            signals.top_category_emission,
            Decimal("0.0000"),
        )

        self.assertEqual(
            signals.category_emissions,
            (),
        )

    @patch(
        "recommendations.services.signals.AnalyticsAggregationService"
    )
    def test_analytics_failure_is_fatal(
        self,
        mock_analytics_service,
    ):
        mock_analytics_service.get_total_emission.side_effect = (
            RuntimeError("Database failure")
        )

        with self.assertRaises(RecommendationSignalError):
            build_recommendation_signals(self.user)

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_kmeans_profile_error_types_are_handled(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(self.user)

        mock_segment_profile.side_effect = UserSegmentProfileError(
            "Segmentation unavailable."
        )

        signals = build_recommendation_signals(self.user)

        self.assertEqual(
            signals.total_emission,
            Decimal("80.0000"),
        )
        self.assertIsNone(signals.user_segment)

    @patch(
        "recommendations.services.signals.get_user_segment_profile"
    )
    def test_weekly_and_monthly_signals_are_preserved(
        self,
        mock_segment_profile,
    ):
        self.create_completed_activity(self.user)

        mock_segment_profile.side_effect = UserSegmentProfileError(
            "K-Means unavailable."
        )

        signals = build_recommendation_signals(self.user)

        self.assertIsInstance(
            signals.monthly_emissions,
            tuple,
        )

        self.assertIsInstance(
            signals.weekly_emissions,
            tuple,
        )