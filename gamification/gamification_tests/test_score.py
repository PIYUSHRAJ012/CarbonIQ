from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from recommendations.models import Recommendation, UserRecommendation

from gamification.services.score import (
    HUNDRED,
    FIFTY,
    calculate_eco_score,
)


class EcoScoreServiceTests(TestCase):
    """
    Tests for the E8 Eco Score service.

    These tests focus on:
    - deterministic scoring
    - score bounds
    - benchmark performance
    - improvement trend
    - sustainable behaviour
    - engagement/progress
    - weighted overall score
    - cold-start handling
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="eco-score@example.com",
            full_name="Eco Score User",
            password="TestPassword123!",
        )

        cls.sustainability_recommendation = (
            Recommendation.objects.create(
                title="Use Public Transport",
                description=(
                    "Prefer public transport for suitable journeys."
                ),
                action_type=Recommendation.ActionType.SUSTAINABILITY,
                priority=50,
                is_active=True,
            )
        )

        cls.offset_recommendation = Recommendation.objects.create(
            title="Support an Offset Project",
            description="Example offset guidance.",
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
            is_active=True,
        )

    def test_cold_start_user_gets_neutral_score(self):
        """
        A user without emissions, recommendations, or history should
        receive a safe neutral score rather than fabricated data.
        """

        result = calculate_eco_score(self.user)

        self.assertEqual(result.emission_performance, FIFTY)
        self.assertEqual(result.improvement_trend, FIFTY)
        self.assertEqual(result.sustainable_behaviour, FIFTY)
        self.assertEqual(result.engagement_progress, FIFTY)
        self.assertEqual(result.overall_score, FIFTY)

    @patch(
        "gamification.services.score._get_latest_monthly_emission",
        return_value=Decimal("100.0000"),
    )
    @patch(
        "gamification.services.score.get_user_monthly_benchmark_comparison",
    )
    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
        return_value=[],
    )
    def test_emission_performance_at_benchmark_scores_fifty(
        self,
        mock_monthly,
        mock_comparison,
        mock_latest,
    ):
        """
        Emissions exactly equal to the benchmark should produce 50.
        """

        mock_comparison.return_value.benchmark_monthly_kg = Decimal(
            "100.0000"
        )

        result = calculate_eco_score(self.user)

        self.assertEqual(result.emission_performance, Decimal("50.00"))

    @patch(
        "gamification.services.score._get_latest_monthly_emission",
        return_value=Decimal("50.0000"),
    )
    @patch(
        "gamification.services.score.get_user_monthly_benchmark_comparison",
    )
    def test_emission_performance_below_benchmark_scores_higher(
        self,
        mock_comparison,
        mock_latest,
    ):
        """
        A lower footprint should receive a higher emission-performance
        score.
        """

        mock_comparison.return_value.benchmark_monthly_kg = Decimal(
            "100.0000"
        )

        result = calculate_eco_score(self.user)

        self.assertEqual(result.emission_performance, Decimal("75.00"))

    @patch(
        "gamification.services.score._get_latest_monthly_emission",
        return_value=Decimal("200.0000"),
    )
    @patch(
        "gamification.services.score.get_user_monthly_benchmark_comparison",
    )
    def test_emission_performance_above_double_benchmark_is_zero(
        self,
        mock_comparison,
        mock_latest,
    ):
        """
        At twice the benchmark, emission performance reaches zero.
        """

        mock_comparison.return_value.benchmark_monthly_kg = Decimal(
            "100.0000"
        )

        result = calculate_eco_score(self.user)

        self.assertEqual(result.emission_performance, Decimal("0.00"))

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
    )
    def test_improvement_trend_rewards_reduction(
        self,
        mock_monthly,
    ):
        """
        A 50% reduction from one month to the next should score 100.
        """

        mock_monthly.return_value = [
            {
                "month": date(2026, 1, 1),
                "total_emission": Decimal("100.0000"),
            },
            {
                "month": date(2026, 2, 1),
                "total_emission": Decimal("50.0000"),
            },
        ]

        result = calculate_eco_score(self.user)

        self.assertEqual(result.improvement_trend, Decimal("100.00"))

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
    )
    def test_improvement_trend_with_no_change_scores_fifty(
        self,
        mock_monthly,
    ):
        """
        No month-to-month change should produce a neutral trend score.
        """

        mock_monthly.return_value = [
            {
                "month": date(2026, 1, 1),
                "total_emission": Decimal("100.0000"),
            },
            {
                "month": date(2026, 2, 1),
                "total_emission": Decimal("100.0000"),
            },
        ]

        result = calculate_eco_score(self.user)

        self.assertEqual(result.improvement_trend, Decimal("50.00"))

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
    )
    def test_improvement_trend_with_increase_scores_lower(
        self,
        mock_monthly,
    ):
        """
        A 20% increase should reduce the trend score to 30.
        """

        mock_monthly.return_value = [
            {
                "month": date(2026, 1, 1),
                "total_emission": Decimal("100.0000"),
            },
            {
                "month": date(2026, 2, 1),
                "total_emission": Decimal("120.0000"),
            },
        ]

        result = calculate_eco_score(self.user)

        self.assertEqual(result.improvement_trend, Decimal("30.00"))

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
        return_value=[],
    )
    def test_improvement_trend_without_history_is_neutral(
        self,
        mock_monthly,
    ):
        """
        Fewer than two months should not create an artificial trend.
        """

        result = calculate_eco_score(self.user)

        self.assertEqual(result.improvement_trend, FIFTY)

    def test_sustainable_behaviour_uses_completed_recommendations(self):
        """
        Completing one of two sustainability recommendations should
        produce a 50% behaviour score.
        """

        first = UserRecommendation.objects.create(
            user=self.user,
            recommendation=self.sustainability_recommendation,
            score=Decimal("80.0000"),
            reason="High transport footprint.",
            status=UserRecommendation.Status.COMPLETED,
        )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=self.sustainability_recommendation,
            score=Decimal("70.0000"),
            reason="Follow-up recommendation.",
            status=UserRecommendation.Status.ACTIVE,
        )

        result = calculate_eco_score(self.user)

        self.assertEqual(
            result.sustainable_behaviour,
            Decimal("50.00"),
        )

        first.delete()

        result_after_delete = calculate_eco_score(self.user)

        self.assertEqual(
            result_after_delete.sustainable_behaviour,
            Decimal("0.00"),
        )

    def test_offset_recommendations_are_excluded_from_behaviour_score(self):
        """
        Offset guidance must not be counted as sustainability-action
        completion for the E8 behaviour component.
        """

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=self.offset_recommendation,
            score=Decimal("90.0000"),
            reason="Offset guidance.",
            status=UserRecommendation.Status.COMPLETED,
        )

        result = calculate_eco_score(self.user)

        self.assertEqual(
            result.sustainable_behaviour,
            FIFTY,
        )

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
    )
    def test_engagement_progress_reaches_hundred_for_three_months(
        self,
        mock_monthly,
    ):
        """
        Three tracked months should produce full engagement/progress.
        """

        mock_monthly.return_value = [
            {
                "month": date(2026, 1, 1),
                "total_emission": Decimal("90.0000"),
            },
            {
                "month": date(2026, 2, 1),
                "total_emission": Decimal("80.0000"),
            },
            {
                "month": date(2026, 3, 1),
                "total_emission": Decimal("70.0000"),
            },
        ]

        result = calculate_eco_score(self.user)

        self.assertEqual(
            result.engagement_progress,
            Decimal("100.00"),
        )

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
    )
    def test_engagement_progress_for_one_month(
        self,
        mock_monthly,
    ):
        """
        One tracked month should produce 33.33.
        """

        mock_monthly.return_value = [
            {
                "month": date(2026, 3, 1),
                "total_emission": Decimal("70.0000"),
            },
        ]

        result = calculate_eco_score(self.user)

        self.assertEqual(
            result.engagement_progress,
            Decimal("33.33"),
        )

    @patch(
        "gamification.services.score.AnalyticsAggregationService.get_monthly_emissions",
        return_value=[],
    )
    def test_engagement_progress_without_history_is_neutral(
        self,
        mock_monthly,
    ):
        result = calculate_eco_score(self.user)

        self.assertEqual(
            result.engagement_progress,
            FIFTY,
        )

    @patch(
        "gamification.services.score._calculate_emission_performance",
        return_value=Decimal("80.00"),
    )
    @patch(
        "gamification.services.score._calculate_improvement_trend",
        return_value=Decimal("60.00"),
    )
    @patch(
        "gamification.services.score._calculate_sustainable_behaviour",
        return_value=Decimal("40.00"),
    )
    @patch(
        "gamification.services.score._calculate_engagement_progress",
        return_value=Decimal("20.00"),
    )
    def test_overall_score_uses_declared_weights(
        self,
        mock_engagement,
        mock_behaviour,
        mock_trend,
        mock_performance,
    ):
        """
        Verify the 40/25/20/15 weighting exactly.
        """

        result = calculate_eco_score(self.user)

        expected = (
            Decimal("80.00") * Decimal("0.40")
            + Decimal("60.00") * Decimal("0.25")
            + Decimal("40.00") * Decimal("0.20")
            + Decimal("20.00") * Decimal("0.15")
        )

        self.assertEqual(
            result.overall_score,
            expected.quantize(Decimal("0.01")),
        )

    def test_score_components_and_overall_are_bounded(self):
        """
        Every returned score must remain inside the 0–100 range.
        """

        result = calculate_eco_score(self.user)

        values = (
            result.overall_score,
            result.emission_performance,
            result.improvement_trend,
            result.sustainable_behaviour,
            result.engagement_progress,
        )

        for value in values:
            self.assertGreaterEqual(value, Decimal("0.00"))
            self.assertLessEqual(value, HUNDRED)

    @patch(
        "gamification.services.score._calculate_emission_performance",
        return_value=Decimal("72.00"),
    )
    @patch(
        "gamification.services.score._calculate_improvement_trend",
        return_value=Decimal("64.00"),
    )
    @patch(
        "gamification.services.score._calculate_sustainable_behaviour",
        return_value=Decimal("88.00"),
    )
    @patch(
        "gamification.services.score._calculate_engagement_progress",
        return_value=Decimal("92.00"),
    )
    def test_score_is_deterministic_for_same_inputs(
        self,
        mock_engagement,
        mock_behaviour,
        mock_trend,
        mock_performance,
    ):
        """
        Same underlying component values must produce the same score.
        """

        first_result = calculate_eco_score(self.user)
        second_result = calculate_eco_score(self.user)

        self.assertEqual(first_result, second_result)