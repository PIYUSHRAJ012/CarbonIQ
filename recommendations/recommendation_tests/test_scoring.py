from decimal import Decimal

from django.test import TestCase

from carbon.models import ActivityCategory
from recommendations.models import Recommendation
from recommendations.services.scoring import (
    calculate_base_priority_score,
    calculate_category_score,
    calculate_recommendation_score,
    calculate_rf_score,
    calculate_segment_score,
    calculate_trend_score,
    normalize_percentage_change,
    rank_recommendations,
)
from recommendations.services.signals import RecommendationSignals


class RecommendationScoringTests(TestCase):
    @classmethod
    def setUpTestData(cls):
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
        title="Reduce electricity consumption",
        category=None,
        action_type=Recommendation.ActionType.SUSTAINABILITY,
        priority=80,
        segment="energy-oriented",
        active=True,
    ):
        return Recommendation.objects.create(
            title=title,
            description="Test recommendation",
            category=category,
            action_type=action_type,
            priority=priority,
            applicable_segment=segment,
            is_active=active,
        )

    # ------------------------------------------------------------------
    # Normalization
    # ------------------------------------------------------------------

    def test_percentage_change_normalization(self):
        self.assertEqual(
            normalize_percentage_change(
                Decimal("-50")
            ),
            Decimal("0"),
        )

        self.assertEqual(
            normalize_percentage_change(
                Decimal("0")
            ),
            Decimal("50"),
        )

        self.assertEqual(
            normalize_percentage_change(
                Decimal("50")
            ),
            Decimal("100"),
        )

    def test_percentage_change_is_clamped(self):
        self.assertEqual(
            normalize_percentage_change(
                Decimal("-100")
            ),
            Decimal("0"),
        )

        self.assertEqual(
            normalize_percentage_change(
                Decimal("100")
            ),
            Decimal("100"),
        )

    # ------------------------------------------------------------------
    # Base priority
    # ------------------------------------------------------------------

    def test_base_priority_is_normalized(self):
        recommendation = self.create_recommendation(
            priority=75,
        )

        self.assertEqual(
            calculate_base_priority_score(
                recommendation
            ),
            Decimal("75"),
        )

    # ------------------------------------------------------------------
    # Category relevance
    # ------------------------------------------------------------------

    def test_category_score_uses_emission_share(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            total="100.0000",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("70.0000"),
                },
                {
                    "category__name": "Transportation",
                    "total_emission": Decimal("30.0000"),
                },
            ],
        )

        self.assertEqual(
            calculate_category_score(
                recommendation,
                signals,
            ),
            Decimal("70.0"),
        )

    def test_missing_category_gets_zero(self):
        recommendation = self.create_recommendation(
            category=self.transportation,
        )

        signals = self.build_signals(
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        self.assertEqual(
            calculate_category_score(
                recommendation,
                signals,
            ),
            Decimal("0"),
        )

    def test_category_independent_recommendation_gets_neutral_score(self):
        recommendation = self.create_recommendation(
            category=None,
            action_type=Recommendation.ActionType.OFFSET,
        )

        signals = self.build_signals()

        self.assertEqual(
            calculate_category_score(
                recommendation,
                signals,
            ),
            Decimal("50"),
        )

    # ------------------------------------------------------------------
    # Trend
    # ------------------------------------------------------------------

    def test_trend_score_is_neutral_without_two_months(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            monthly_rows=[
                {
                    "month": "2026-08",
                    "total_emission": Decimal("100"),
                }
            ],
        )

        self.assertEqual(
            calculate_trend_score(
                recommendation,
                signals,
            ),
            Decimal("50"),
        )

    def test_trend_score_for_stable_emissions(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            monthly_rows=[
                {
                    "month": "2026-07",
                    "total_emission": Decimal("100"),
                },
                {
                    "month": "2026-08",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        self.assertEqual(
            calculate_trend_score(
                recommendation,
                signals,
            ),
            Decimal("50"),
        )

    def test_trend_score_for_increasing_emissions(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            monthly_rows=[
                {
                    "month": "2026-07",
                    "total_emission": Decimal("100"),
                },
                {
                    "month": "2026-08",
                    "total_emission": Decimal("125"),
                },
            ],
        )

        self.assertEqual(
            calculate_trend_score(
                recommendation,
                signals,
            ),
            Decimal("75"),
        )

    # ------------------------------------------------------------------
    # Random Forest
    # ------------------------------------------------------------------

    def test_rf_score_is_neutral_when_unavailable(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            total="100",
            rf_prediction=None,
        )

        self.assertEqual(
            calculate_rf_score(
                recommendation,
                signals,
            ),
            Decimal("50"),
        )

    def test_rf_score_for_increasing_prediction(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            total="100",
            rf_prediction=Decimal("120"),
        )

        self.assertEqual(
            calculate_rf_score(
                recommendation,
                signals,
            ),
            Decimal("70"),
        )

    # ------------------------------------------------------------------
    # K-Means
    # ------------------------------------------------------------------

    def test_segment_score_is_neutral_when_unavailable(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            domain_scores=None,
        )

        self.assertEqual(
            calculate_segment_score(
                recommendation,
                signals,
            ),
            Decimal("50"),
        )

    def test_segment_score_uses_relative_domain_strength(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
        )

        signals = self.build_signals(
            domain_scores={
                "energy": 2.0,
                "transport": 1.0,
                "food": 1.0,
            },
        )

        self.assertEqual(
            calculate_segment_score(
                recommendation,
                signals,
            ),
            Decimal("100"),
        )

    def test_segment_score_for_lower_domain_strength(self):
        recommendation = self.create_recommendation(
            title="Reduce transportation emissions",
            category=self.transportation,
        )

        signals = self.build_signals(
            domain_scores={
                "energy": 2.0,
                "transport": 1.0,
                "food": 1.0,
            },
        )

        self.assertEqual(
            calculate_segment_score(
                recommendation,
                signals,
            ),
            Decimal("50"),
        )

    # ------------------------------------------------------------------
    # Applicability / final score
    # ------------------------------------------------------------------

    def test_inactive_recommendation_is_not_applicable(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
            active=False,
        )

        signals = self.build_signals(
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        result = calculate_recommendation_score(
            recommendation,
            signals,
        )

        self.assertFalse(result.applicable)
        self.assertEqual(
            result.score,
            Decimal("0.0000"),
        )

    def test_zero_emission_category_is_not_applicable(self):
        recommendation = self.create_recommendation(
            category=self.transportation,
        )

        signals = self.build_signals(
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        result = calculate_recommendation_score(
            recommendation,
            signals,
        )

        self.assertFalse(result.applicable)
        self.assertEqual(
            result.score,
            Decimal("0.0000"),
        )

    def test_offset_is_secondary(self):
        recommendation = self.create_recommendation(
            category=None,
            action_type=Recommendation.ActionType.OFFSET,
            priority=100,
        )

        signals = self.build_signals(
            total="100",
        )

        result = calculate_recommendation_score(
            recommendation,
            signals,
        )

        self.assertTrue(result.applicable)
        self.assertLessEqual(
            result.score,
            Decimal("60"),
        )

    def test_full_score_uses_all_available_signals(self):
        recommendation = self.create_recommendation(
            category=self.electricity,
            priority=100,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
            monthly_rows=[
                {
                    "month": "2026-07",
                    "total_emission": Decimal("100"),
                },
                {
                    "month": "2026-08",
                    "total_emission": Decimal("150"),
                },
            ],
            rf_prediction=150,
            domain_scores={
                "energy": 2.0,
                "transport": 1.0,
                "food": 1.0,
            },
        )

        result = calculate_recommendation_score(
            recommendation,
            signals,
        )

        self.assertTrue(result.applicable)

        self.assertEqual(
            result.base_priority_score,
            Decimal("100"),
        )

        self.assertEqual(
            result.category_score,
            Decimal("100"),
        )

        self.assertEqual(
            result.trend_score,
            Decimal("100"),
        )

        self.assertEqual(
            result.rf_score,
            Decimal("100"),
        )

        self.assertEqual(
            result.segment_score,
            Decimal("100"),
        )

        self.assertEqual(
            result.score,
            Decimal("100.0000"),
        )

    # ------------------------------------------------------------------
    # Ranking
    # ------------------------------------------------------------------

    def test_ranking_places_higher_score_first(self):
        high = self.create_recommendation(
            title="High priority",
            category=self.electricity,
            priority=90,
        )

        low = self.create_recommendation(
            title="Low priority",
            category=self.transportation,
            priority=20,
        )

        signals = self.build_signals(
            total="100",
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("80"),
                },
                {
                    "category__name": "Transportation",
                    "total_emission": Decimal("20"),
                },
            ],
        )

        ranked = rank_recommendations(
            [low, high],
            signals,
        )

        self.assertIs(
            ranked[0].recommendation,
            high,
        )

    def test_ranking_is_deterministic(self):
        first = self.create_recommendation(
            title="Alpha",
            category=self.electricity,
            priority=50,
        )

        second = self.create_recommendation(
            title="Beta",
            category=self.electricity,
            priority=50,
        )

        signals = self.build_signals(
            category_rows=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("100"),
                },
            ],
        )

        ranked = rank_recommendations(
            [second, first],
            signals,
        )

        self.assertEqual(
            ranked[0].recommendation.title,
            "Alpha",
        )

        self.assertEqual(
            ranked[1].recommendation.title,
            "Beta",
        )