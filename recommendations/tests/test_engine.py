from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import ActivityCategory
from recommendations.models import Recommendation, UserRecommendation
from recommendations.services.engine import (
    RecommendationEngineError,
    generate_user_recommendations,
)
from recommendations.services.signals import RecommendationSignals


class RecommendationEngineTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="engine@example.com",
            full_name="Engine Test User",
            password="TestPassword123!",
        )

        cls.other_user = CustomUser.objects.create_user(
            email="other-engine@example.com",
            full_name="Other Engine User",
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

    @staticmethod
    def build_signals(
        total="100.0000",
        category_rows=None,
        monthly_rows=None,
        rf_prediction=None,
        domain_scores=None,
    ):
        return RecommendationSignals(
            total_emission=Decimal(total),
            category_emissions=tuple(category_rows or ()),
            monthly_emissions=tuple(monthly_rows or ()),
            weekly_emissions=(),
            top_category=(
                category_rows[0]["category__name"]
                if category_rows
                else None
            ),
            top_category_emission=(
                Decimal(
                    str(category_rows[0]["total_emission"])
                )
                if category_rows
                else Decimal("0.0000")
            ),
            rf_prediction=rf_prediction,
            user_segment=(
                "Energy-oriented"
                if domain_scores
                else None
            ),
            dominant_domain=(
                "energy"
                if domain_scores
                else None
            ),
            segment_domain_scores=domain_scores,
            segment_feature_strengths=(
                {"electricity": 2.0}
                if domain_scores
                else None
            ),
            segment_model_version=(
                "kmeans-v1"
                if domain_scores
                else None
            ),
            segment_selected_k=(
                3
                if domain_scores
                else None
            ),
        )

    def create_recommendation(
        self,
        title,
        category=None,
        action_type=Recommendation.ActionType.SUSTAINABILITY,
        priority=80,
        segment="",
        active=True,
    ):
        return Recommendation.objects.create(
            title=title,
            description=f"Test description for {title}.",
            category=category,
            action_type=action_type,
            priority=priority,
            applicable_segment=segment,
            is_active=active,
        )

    def create_catalog(self):
        return [
            self.create_recommendation(
                title="Reduce electricity consumption",
                category=self.electricity,
                priority=90,
                segment="energy-oriented",
            ),
            self.create_recommendation(
                title="Improve energy efficiency",
                category=self.electricity,
                priority=80,
                segment="energy-oriented",
            ),
            self.create_recommendation(
                title="Reduce private vehicle usage",
                category=self.transportation,
                priority=85,
                segment="transport-oriented",
            ),
            self.create_recommendation(
                title="Improve waste segregation",
                category=None,
                priority=70,
                segment="",
            ),
            self.create_recommendation(
                title="Consider verified carbon offsets",
                category=None,
                action_type=Recommendation.ActionType.OFFSET,
                priority=50,
            ),
        ]

    # ------------------------------------------------------------------
    # Basic generation
    # ------------------------------------------------------------------

    @patch(
        "recommendations.services.engine.build_recommendation_signals"
    )
    def test_generates_user_recommendations(
        self,
        mock_build_signals,
    ):
        self.create_catalog()

        mock_build_signals.return_value = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("70"),
                },
                {
                    "category__name": "Transportation",
                    "total_emission": Decimal("30"),
                },
            ],
        )

        results = generate_user_recommendations(
            self.user
        )

        self.assertTrue(results)

        self.assertTrue(
            UserRecommendation.objects.filter(
                user=self.user,
                status=UserRecommendation.Status.ACTIVE,
            ).exists()
        )

    def test_maximum_sustainability_recommendations_is_five(self):
        for index in range(8):
            self.create_recommendation(
                title=f"Electricity action {index}",
                category=self.electricity,
                priority=80 - index,
            )

        self.create_recommendation(
            title="Offset action",
            category=None,
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                }
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            generate_user_recommendations(
                self.user
            )

        sustainability_count = (
            UserRecommendation.objects.filter(
                user=self.user,
                status=UserRecommendation.Status.ACTIVE,
                recommendation__action_type=(
                    Recommendation.ActionType.SUSTAINABILITY
                ),
            ).count()
        )

        self.assertEqual(
            sustainability_count,
            5,
        )

    def test_maximum_offset_recommendations_is_two(self):
        for index in range(5):
            self.create_recommendation(
                title=f"Offset action {index}",
                category=None,
                action_type=Recommendation.ActionType.OFFSET,
                priority=50,
            )

        signals = self.build_signals(
            total="100",
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            generate_user_recommendations(
                self.user
            )

        offset_count = (
            UserRecommendation.objects.filter(
                user=self.user,
                status=UserRecommendation.Status.ACTIVE,
                recommendation__action_type=(
                    Recommendation.ActionType.OFFSET
                ),
            ).count()
        )

        self.assertEqual(
            offset_count,
            2,
        )

    # ------------------------------------------------------------------
    # Reasons
    # ------------------------------------------------------------------

    def test_reason_is_generated(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
            priority=90,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("80"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            results = generate_user_recommendations(
                self.user
            )

        self.assertEqual(
            len(results),
            1,
        )

        user_recommendation = results[0].user_recommendation

        self.assertTrue(
            user_recommendation.reason
        )

        self.assertIn(
            "Electricity",
            user_recommendation.reason,
        )

    def test_offset_reason_is_explanatory(self):
        self.create_recommendation(
            title="Consider verified carbon offsets",
            category=None,
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
        )

        signals = self.build_signals(
            total="100",
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            results = generate_user_recommendations(
                self.user
            )

        self.assertEqual(
            len(results),
            1,
        )

        self.assertIn(
            "complementary",
            results[0].user_recommendation.reason.lower(),
        )

    # ------------------------------------------------------------------
    # Regeneration lifecycle
    # ------------------------------------------------------------------

    def test_previous_active_recommendations_become_superseded(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        old_result = UserRecommendation.objects.create(
            user=self.user,
            recommendation=recommendation,
            score=Decimal("70.0000"),
            reason="Previous generation.",
            status=UserRecommendation.Status.ACTIVE,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            generate_user_recommendations(
                self.user
            )

        old_result.refresh_from_db()

        self.assertEqual(
            old_result.status,
            UserRecommendation.Status.SUPERSEDED,
        )

    def test_dismissed_recommendations_are_preserved(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        dismissed = UserRecommendation.objects.create(
            user=self.user,
            recommendation=recommendation,
            score=Decimal("70.0000"),
            reason="User dismissed this recommendation.",
            status=UserRecommendation.Status.DISMISSED,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            generate_user_recommendations(
                self.user
            )

        dismissed.refresh_from_db()

        self.assertEqual(
            dismissed.status,
            UserRecommendation.Status.DISMISSED,
        )

    def test_completed_recommendations_are_preserved(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        completed = UserRecommendation.objects.create(
            user=self.user,
            recommendation=recommendation,
            score=Decimal("70.0000"),
            reason="User completed this recommendation.",
            status=UserRecommendation.Status.COMPLETED,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            generate_user_recommendations(
                self.user
            )

        completed.refresh_from_db()

        self.assertEqual(
            completed.status,
            UserRecommendation.Status.COMPLETED,
        )

    def test_second_generation_replaces_previous_active_set(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            first_results = generate_user_recommendations(
                self.user
            )

            second_results = generate_user_recommendations(
                self.user
            )

        self.assertEqual(
            len(first_results),
            1,
        )

        self.assertEqual(
            len(second_results),
            1,
        )

        active_count = (
            UserRecommendation.objects.filter(
                user=self.user,
                status=UserRecommendation.Status.ACTIVE,
            ).count()
        )

        superseded_count = (
            UserRecommendation.objects.filter(
                user=self.user,
                status=UserRecommendation.Status.SUPERSEDED,
            ).count()
        )

        self.assertEqual(
            active_count,
            1,
        )

        self.assertEqual(
            superseded_count,
            1,
        )

    # ------------------------------------------------------------------
    # Applicability
    # ------------------------------------------------------------------

    def test_inapplicable_categories_are_not_generated(self):
        electricity_recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        self.create_recommendation(
            title="Reduce transportation emissions",
            category=self.transportation,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            results = generate_user_recommendations(
                self.user
            )

        generated_ids = {
            result.user_recommendation.recommendation_id
            for result in results
        }

        self.assertIn(
            electricity_recommendation.id,
            generated_ids,
        )

        transportation_count = (
            UserRecommendation.objects.filter(
                user=self.user,
                recommendation__category=self.transportation,
                status=UserRecommendation.Status.ACTIVE,
            ).count()
        )

        self.assertEqual(
            transportation_count,
            0,
        )

    def test_zero_emission_user_gets_no_offset_recommendations(self):
        self.create_recommendation(
            title="Consider verified carbon offsets",
            category=None,
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
        )

        signals = self.build_signals(
            total="0",
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            results = generate_user_recommendations(
                self.user
            )

        self.assertEqual(
            len(results),
            0,
        )

    # ------------------------------------------------------------------
    # User isolation
    # ------------------------------------------------------------------

    def test_recommendations_belong_to_requested_user(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ):
            results = generate_user_recommendations(
                self.user
            )

        self.assertEqual(
            len(results),
            1,
        )

        result = results[0].user_recommendation

        self.assertEqual(
            result.user_id,
            self.user.id,
        )

        self.assertEqual(
            result.recommendation_id,
            recommendation.id,
        )

        self.assertFalse(
            UserRecommendation.objects.filter(
                user=self.other_user
            ).exists()
        )

    # ------------------------------------------------------------------
    # Error handling / transaction rollback
    # ------------------------------------------------------------------

    def test_signal_failure_raises_engine_error(self):
        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            side_effect=RuntimeError(
                "Signal generation failed."
            ),
        ):
            with self.assertRaises(
                RecommendationEngineError
            ):
                generate_user_recommendations(
                    self.user
                )

    def test_generation_failure_rolls_back_superseding(self):
        recommendation = self.create_recommendation(
            title="Reduce electricity consumption",
            category=self.electricity,
        )

        old_result = UserRecommendation.objects.create(
            user=self.user,
            recommendation=recommendation,
            score=Decimal("80.0000"),
            reason="Existing recommendation.",
            status=UserRecommendation.Status.ACTIVE,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        with patch(
            "recommendations.services.engine.build_recommendation_signals",
            return_value=signals,
        ), patch(
            "recommendations.services.engine.UserRecommendation.objects.create",
            side_effect=RuntimeError(
                "Database write failed."
            ),
        ):
            with self.assertRaises(
                RecommendationEngineError
            ):
                generate_user_recommendations(
                    self.user
                )

        old_result.refresh_from_db()

        self.assertEqual(
            old_result.status,
            UserRecommendation.Status.ACTIVE,
        )