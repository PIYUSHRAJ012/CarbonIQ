from datetime import date
from decimal import Decimal
from unittest.mock import patch

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
from recommendations.models import (
    OffsetProject,
    OffsetRecommendation,
)
from recommendations.services.offset_recommendations import (
    OffsetRecommendationError,
    generate_offset_recommendations,
)
from recommendations.services.signals import RecommendationSignals


class OffsetRecommendationServiceTests(TestCase):
    """
    Tests for the E5 offset recommendation generation service.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="user@example.com",
            full_name="Test User",
            password="test-password-123",
        )

        self.other_user = CustomUser.objects.create_user(
            email="other@example.com",
            full_name="Other User",
            password="test-password-123",
        )

        self.category = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        self.factor = EmissionFactor.objects.create(
            activity_category=self.category,
            factor=Decimal("0.8400"),
            source="Test Source",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            is_active=True,
        )

        self.project_one = OffsetProject.objects.create(
            name="Solar Energy Project",
            description=(
                "Renewable solar energy project in India "
                "supporting clean energy."
            ),
            project_type="Renewable Energy",
            country="India",
            region="Karnataka",
            registry="Gold Standard",
            registry_project_id="GS10001",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/10001"
            ),
            standard="Gold Standard",
            status="ACTIVE",
            project_scale="Large",
            annual_estimated_credits=Decimal("10000"),
            sdg_impacts=[
                {"sdg": 7},
                {"sdg": 13},
            ],
            project_developer="Developer One",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        self.project_two = OffsetProject.objects.create(
            name="Wind Energy Project",
            description=(
                "Wind renewable energy project supporting "
                "clean electricity generation."
            ),
            project_type="Renewable Energy",
            country="India",
            region="Tamil Nadu",
            registry="Gold Standard",
            registry_project_id="GS10002",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/10002"
            ),
            standard="Gold Standard",
            status="ACTIVE",
            project_scale="Large",
            annual_estimated_credits=Decimal("12000"),
            sdg_impacts=[
                {"sdg": 13},
            ],
            project_developer="Developer Two",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _build_signals(
        self,
        *,
        total_emission=Decimal("840.0000"),
        monthly_emissions=None,
        category_emissions=None,
    ):
        """
        Build deterministic E3 recommendation signals for service tests.

        ML fields remain optional because E5 must work without
        a trained production ML artifact.
        """

        if monthly_emissions is None:
            monthly_emissions = [
                {
                    "month": date(2026, 8, 1),
                    "total_emission": total_emission,
                }
            ]

        if category_emissions is None:
            category_emissions = [
                {
                    "category__name": "Electricity",
                    "total_emission": total_emission,
                }
            ]

        return RecommendationSignals(
            total_emission=total_emission,
            category_emissions=tuple(category_emissions),
            monthly_emissions=tuple(monthly_emissions),
            weekly_emissions=(),
            top_category="Electricity",
            top_category_emission=total_emission,
            rf_prediction=None,
            user_segment=None,
            dominant_domain="energy",
            segment_domain_scores=None,
            segment_feature_strengths=None,
            segment_model_version=None,
            segment_selected_k=None,
        )

    def _create_completed_footprint(
        self,
        *,
        user=None,
        total_emission=Decimal("840.0000"),
    ):
        """
        Create a valid completed CarbonIQ submission.

        CarbonActivity
            -> ActivityEntry
                -> EmissionFactor
            -> CarbonFootprint
        """

        if user is None:
            user = self.user

        activity = CarbonActivity.objects.create(
            user=user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.category,
            emission_factor=self.factor,
            quantity=Decimal("100.00"),
            emission_factor_snapshot=Decimal("0.8400"),
            entry_emission=total_emission,
        )

        footprint = CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=total_emission,
        )

        return footprint

    # ------------------------------------------------------------------
    # Validation
    # ------------------------------------------------------------------

    def test_none_user_raises_error(self):
        with self.assertRaises(OffsetRecommendationError):
            generate_offset_recommendations(None)

    def test_non_positive_limit_raises_error(self):
        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals"
        ) as build_signals:
            with self.assertRaises(OffsetRecommendationError):
                generate_offset_recommendations(
                    self.user,
                    limit=0,
                )

            build_signals.assert_not_called()

    # ------------------------------------------------------------------
    # No requirement / no data
    # ------------------------------------------------------------------

    def test_no_footprint_returns_empty_list(self):
        signals = self._build_signals(
            total_emission=Decimal("0.0000"),
            monthly_emissions=[],
            category_emissions=[],
        )

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertEqual(result, [])

        self.assertEqual(
            OffsetRecommendation.objects.filter(
                user=self.user
            ).count(),
            0,
        )

    # ------------------------------------------------------------------
    # Recommendation generation
    # ------------------------------------------------------------------

    def test_generates_recommendations(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertGreater(
            len(result),
            0,
        )

        self.assertLessEqual(
            len(result),
            5,
        )

        recommendations = OffsetRecommendation.objects.filter(
            user=self.user
        )

        self.assertEqual(
            recommendations.count(),
            len(result),
        )

        for generated in result:
            recommendation = generated.offset_recommendation

            self.assertEqual(
                recommendation.user,
                self.user,
            )

            self.assertEqual(
                recommendation.status,
                OffsetRecommendation.Status.ACTIVE,
            )

            self.assertGreaterEqual(
                recommendation.score,
                Decimal("0"),
            )

            self.assertLessEqual(
                recommendation.score,
                Decimal("100"),
            )

            self.assertGreater(
                recommendation.indicative_tonnes,
                Decimal("0"),
            )

    def test_limit_is_respected(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user,
                limit=1,
            )

        self.assertEqual(
            len(result),
            1,
        )

        self.assertEqual(
            OffsetRecommendation.objects.filter(
                user=self.user,
                status=OffsetRecommendation.Status.ACTIVE,
            ).count(),
            1,
        )

    # ------------------------------------------------------------------
    # Project filtering
    # ------------------------------------------------------------------

    def test_only_active_projects_are_recommended(self):
        self.project_two.is_active = False
        self.project_two.save(
            update_fields=["is_active"]
        )

        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertGreater(
            len(result),
            0,
        )

        for generated in result:
            project = (
                generated
                .offset_recommendation
                .offset_project
            )

            self.assertTrue(
                project.is_active
            )

            self.assertEqual(
                project.status,
                "ACTIVE",
            )

    def test_non_active_project_status_is_excluded(self):
        self.project_two.status = "COMPLETED"
        self.project_two.save(
            update_fields=["status"]
        )

        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertGreater(
            len(result),
            0,
        )

        for generated in result:
            project = (
                generated
                .offset_recommendation
                .offset_project
            )

            self.assertEqual(
                project.status,
                "ACTIVE",
            )

    # ------------------------------------------------------------------
    # Recommendation lifecycle
    # ------------------------------------------------------------------

    def test_active_recommendations_are_superseded(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            first_result = generate_offset_recommendations(
                self.user
            )

            self.assertGreater(
                len(first_result),
                0,
            )

            first_active_count = (
                OffsetRecommendation.objects.filter(
                    user=self.user,
                    status=(
                        OffsetRecommendation
                        .Status.ACTIVE
                    ),
                ).count()
            )

            self.assertEqual(
                first_active_count,
                len(first_result),
            )

            second_result = (
                generate_offset_recommendations(
                    self.user
                )
            )

        self.assertGreater(
            len(second_result),
            0,
        )

        superseded_count = (
            OffsetRecommendation.objects.filter(
                user=self.user,
                status=(
                    OffsetRecommendation
                    .Status.SUPERSEDED
                ),
            ).count()
        )

        self.assertEqual(
            superseded_count,
            first_active_count,
        )

        active_count = (
            OffsetRecommendation.objects.filter(
                user=self.user,
                status=(
                    OffsetRecommendation
                    .Status.ACTIVE
                ),
            ).count()
        )

        self.assertEqual(
            active_count,
            len(second_result),
        )

    def test_dismissed_recommendations_are_preserved(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            first_result = generate_offset_recommendations(
                self.user
            )

            self.assertGreater(
                len(first_result),
                0,
            )

            recommendation = (
                first_result[0]
                .offset_recommendation
            )

            recommendation.status = (
                OffsetRecommendation.Status.DISMISSED
            )

            recommendation.save(
                update_fields=["status"]
            )

            generate_offset_recommendations(
                self.user
            )

        recommendation.refresh_from_db()

        self.assertEqual(
            recommendation.status,
            OffsetRecommendation.Status.DISMISSED,
        )

    def test_completed_recommendations_are_preserved(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            first_result = generate_offset_recommendations(
                self.user
            )

            self.assertGreater(
                len(first_result),
                0,
            )

            recommendation = (
                first_result[0]
                .offset_recommendation
            )

            recommendation.status = (
                OffsetRecommendation.Status.COMPLETED
            )

            recommendation.save(
                update_fields=["status"]
            )

            generate_offset_recommendations(
                self.user
            )

        recommendation.refresh_from_db()

        self.assertEqual(
            recommendation.status,
            OffsetRecommendation.Status.COMPLETED,
        )

    # ------------------------------------------------------------------
    # User isolation
    # ------------------------------------------------------------------

    def test_recommendations_are_isolated_by_user(self):
        self._create_completed_footprint(
            user=self.user
        )

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertGreater(
            len(result),
            0,
        )

        self.assertEqual(
            OffsetRecommendation.objects.filter(
                user=self.user
            ).count(),
            len(result),
        )

        self.assertEqual(
            OffsetRecommendation.objects.filter(
                user=self.other_user
            ).count(),
            0,
        )

    # ------------------------------------------------------------------
    # Explanation / indicative requirement
    # ------------------------------------------------------------------

    def test_reason_contains_offset_guidance(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertGreater(
            len(result),
            0,
        )

        reason = (
            result[0]
            .offset_recommendation
            .reason
        )

        self.assertIn(
            "indicative offset requirement",
            reason,
        )

        self.assertIn(
            "Reducing emissions remains the primary",
            reason,
        )

    def test_indicative_tonnes_are_stored(self):
        self._create_completed_footprint(
            total_emission=Decimal("840.0000")
        )

        signals = self._build_signals(
            total_emission=Decimal("840.0000")
        )

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user
            )

        self.assertGreater(
            len(result),
            0,
        )

        for generated in result:
            recommendation = (
                generated.offset_recommendation
            )

            self.assertEqual(
                recommendation.indicative_tonnes,
                generated.requirement.indicative_tonnes,
            )

        self.assertEqual(
            result[0]
            .requirement
            .indicative_tonnes,
            Decimal("0.8400"),
        )

    def test_recommendation_projects_are_unique(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            result = generate_offset_recommendations(
                self.user,
                limit=5,
            )

        project_ids = [
            generated
            .offset_recommendation
            .offset_project_id
            for generated in result
        ]

        self.assertEqual(
            len(project_ids),
            len(set(project_ids)),
        )

    # ------------------------------------------------------------------
    # Safe failure handling
    # ------------------------------------------------------------------

    def test_signal_build_failure_is_wrapped(self):
        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            side_effect=RuntimeError("signal failure"),
        ):
            with self.assertRaises(
                OffsetRecommendationError
            ) as context:
                generate_offset_recommendations(
                    self.user
                )

        self.assertEqual(
            str(context.exception),
            "Unable to build recommendation signals "
            "for offset guidance.",
        )

    def test_project_ranking_failure_is_wrapped(self):
        self._create_completed_footprint()

        signals = self._build_signals()

        with patch(
            "recommendations.services.offset_recommendations."
            "build_recommendation_signals",
            return_value=signals,
        ):
            with patch(
                "recommendations.services.offset_recommendations."
                "rank_offset_projects",
                side_effect=RuntimeError(
                    "ranking failure"
                ),
            ):
                with self.assertRaises(
                    OffsetRecommendationError
                ) as context:
                    generate_offset_recommendations(
                        self.user
                    )

        self.assertEqual(
            str(context.exception),
            "Unable to rank available offset projects.",
        )