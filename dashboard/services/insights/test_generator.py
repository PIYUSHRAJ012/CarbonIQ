from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal

from django.test import SimpleTestCase

from dashboard.services.insights.contracts import InsightType
from dashboard.services.insights.generator import generate_insights
from dashboard.services.insights.signals import (
    ExternalEnvironmentSignal,
    InsightSignals,
)


@dataclass(frozen=True)
class FakePrediction:
    predicted_emission: float
    feature_period: date
    target_period: date
    model_version: str | None


@dataclass(frozen=True)
class FakeSegment:
    user_id: int
    cluster_id: int
    profile_name: str
    dominant_domain: str
    model_version: str
    selected_k: int
    domain_scores: dict[str, float]
    feature_strengths: dict[str, float]


@dataclass(frozen=True)
class FakeMonthlyComparison:
    month: str
    personal_emission_kg: Decimal
    benchmark_emission_kg: Decimal
    difference_kg: Decimal
    difference_percent: Decimal
    below_benchmark: bool


@dataclass(frozen=True)
class FakeBenchmark:
    benchmark_monthly_kg: Decimal
    personal_monthly_comparisons: tuple[
        FakeMonthlyComparison,
        ...,
    ]


@dataclass(frozen=True)
class FakeRecommendation:
    title: str
    description: str = "Test recommendation."


@dataclass(frozen=True)
class FakeUserRecommendation:
    recommendation: FakeRecommendation
    reason: str
    score: Decimal


class InsightGeneratorTests(SimpleTestCase):
    def make_signals(self, **overrides):
        values = {
            "current_total_emission": Decimal("100.0000"),
            "monthly_emissions": (
                {
                    "month": datetime(
                        2026,
                        8,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("80.0000"),
                },
                {
                    "month": datetime(
                        2026,
                        9,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("100.0000"),
                },
            ),
            "weekly_emissions": (),
            "category_emissions": (),
            "top_category": None,
            "top_category_emission": None,
            "prediction": None,
            "user_segment": None,
            "recommendations": (),
            "benchmark": None,
            "offset_context": (),
            "external_environment": None,
        }

        values.update(overrides)

        return InsightSignals(**values)

    def get(self, insights, insight_type):
        matches = [
            item
            for item in insights
            if item.type == insight_type
        ]

        self.assertEqual(len(matches), 1)

        return matches[0]

    def test_empty_signals_return_empty_tuple(self):
        signals = self.make_signals(
            current_total_emission=Decimal("0"),
            monthly_emissions=(),
        )

        self.assertEqual(
            generate_insights(signals),
            (),
        )

    def test_trend_increase(self):
        insight = self.get(
            generate_insights(self.make_signals()),
            InsightType.TREND,
        )

        self.assertEqual(
            insight.title,
            "Your carbon footprint is increasing",
        )

        self.assertEqual(
            insight.metric,
            Decimal("100.0000"),
        )

    def test_trend_decrease(self):
        signals = self.make_signals(
            monthly_emissions=(
                {
                    "month": datetime(
                        2026,
                        8,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("100.0000"),
                },
                {
                    "month": datetime(
                        2026,
                        9,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("80.0000"),
                },
            )
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.TREND,
        )

        self.assertEqual(
            insight.title,
            "Your carbon footprint is decreasing",
        )

    def test_stable_trend(self):
        signals = self.make_signals(
            monthly_emissions=(
                {
                    "month": datetime(
                        2026,
                        8,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("100.0000"),
                },
                {
                    "month": datetime(
                        2026,
                        9,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("100.0000"),
                },
            )
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.TREND,
        )

        self.assertEqual(
            insight.title,
            "Your carbon footprint is stable",
        )

    def test_insufficient_monthly_history_has_no_trend(self):
        signals = self.make_signals(
            monthly_emissions=(
                {
                    "month": datetime(
                        2026,
                        9,
                        1,
                        tzinfo=timezone.utc,
                    ),
                    "total_emission": Decimal("100.0000"),
                },
            )
        )

        insights = generate_insights(signals)

        self.assertFalse(
            any(
                item.type == InsightType.TREND
                for item in insights
            )
        )

    def test_emission_driver(self):
        signals = self.make_signals(
            top_category="Electricity",
            top_category_emission=Decimal("70.0000"),
            current_total_emission=Decimal("100.0000"),
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.EMISSION_DRIVER,
        )

        self.assertIn(
            "Electricity",
            insight.title,
        )

        self.assertEqual(
            insight.metric,
            Decimal("70.0000"),
        )

        self.assertIn(
            "70.0%",
            insight.message,
        )

    def test_zero_total_emission_does_not_divide(self):
        signals = self.make_signals(
            current_total_emission=Decimal("0"),
            top_category="Electricity",
            top_category_emission=Decimal("10"),
        )

        insights = generate_insights(signals)

        self.assertFalse(
            any(
                item.type == InsightType.EMISSION_DRIVER
                for item in insights
            )
        )

    def test_prediction_only_when_available(self):
        signals = self.make_signals(
            prediction=FakePrediction(
                predicted_emission=123.45,
                feature_period=date(
                    2026,
                    9,
                    1,
                ),
                target_period=date(
                    2026,
                    10,
                    1,
                ),
                model_version="rf-v1",
            )
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.PREDICTION,
        )

        self.assertEqual(
            insight.metric,
            Decimal("123.45"),
        )

        self.assertIn(
            "October 2026",
            insight.message,
        )

        self.assertIn(
            "rf-v1",
            insight.message,
        )

    def test_prediction_none_creates_no_prediction_insight(self):
        insights = generate_insights(
            self.make_signals(
                prediction=None,
            )
        )

        self.assertFalse(
            any(
                item.type == InsightType.PREDICTION
                for item in insights
            )
        )

    def test_segment_only_when_available(self):
        signals = self.make_signals(
            user_segment=FakeSegment(
                user_id=1,
                cluster_id=2,
                profile_name="Balanced Sustainer",
                dominant_domain="Electricity",
                model_version="kmeans-v1",
                selected_k=3,
                domain_scores={},
                feature_strengths={},
            )
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.SEGMENT,
        )

        self.assertIn(
            "Balanced Sustainer",
            insight.message,
        )

        self.assertIn(
            "Electricity",
            insight.message,
        )

    def test_segment_none_creates_no_segment_insight(self):
        insights = generate_insights(
            self.make_signals(
                user_segment=None,
            )
        )

        self.assertFalse(
            any(
                item.type == InsightType.SEGMENT
                for item in insights
            )
        )

    def test_benchmark_below(self):
        signals = self.make_signals(
            benchmark=FakeBenchmark(
                benchmark_monthly_kg=Decimal("50.0000"),
                personal_monthly_comparisons=(
                    FakeMonthlyComparison(
                        month="2026-09",
                        personal_emission_kg=Decimal("40.0000"),
                        benchmark_emission_kg=Decimal("50.0000"),
                        difference_kg=Decimal("-10.0000"),
                        difference_percent=Decimal("-20.0000"),
                        below_benchmark=True,
                    ),
                ),
            )
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.BENCHMARK,
        )

        self.assertEqual(
            insight.title,
            "You are below your benchmark",
        )

        self.assertIn(
            "20.0%",
            insight.message,
        )

    def test_benchmark_above(self):
        signals = self.make_signals(
            benchmark=FakeBenchmark(
                benchmark_monthly_kg=Decimal("50.0000"),
                personal_monthly_comparisons=(
                    FakeMonthlyComparison(
                        month="2026-09",
                        personal_emission_kg=Decimal("75.0000"),
                        benchmark_emission_kg=Decimal("50.0000"),
                        difference_kg=Decimal("25.0000"),
                        difference_percent=Decimal("50.0000"),
                        below_benchmark=False,
                    ),
                ),
            )
        )

        insight = self.get(
            generate_insights(signals),
            InsightType.BENCHMARK,
        )

        self.assertEqual(
            insight.title,
            "Your footprint is above your benchmark",
        )

    def test_missing_benchmark_has_no_insight(self):
        insights = generate_insights(
            self.make_signals(
                benchmark=None,
            )
        )

        self.assertFalse(
            any(
                item.type == InsightType.BENCHMARK
                for item in insights
            )
        )

    def test_measured_external_environment(self):
        environment = ExternalEnvironmentSignal(
            provider="India Energy Atlas",
            zone="Karnataka",
            value=Decimal("335.3200"),
            unit="gCO2e/kWh",
            observed_at=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            fetched_at=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            is_estimated=False,
            estimation_method="",
            temporal_granularity="hourly",
            emission_factor_type="lifecycle",
            source_url="https://example.com",
        )

        insight = self.get(
            generate_insights(
                self.make_signals(
                    external_environment=environment,
                )
            ),
            InsightType.ENVIRONMENTAL_CONTEXT,
        )

        self.assertIn(
            "335.32",
            insight.message,
        )

        self.assertIn(
            "India Energy Atlas",
            insight.message,
        )

    def test_estimated_external_environment_is_explicit(self):
        environment = ExternalEnvironmentSignal(
            provider="India Energy Atlas",
            zone="Karnataka",
            value=Decimal("335.3200"),
            unit="gCO2e/kWh",
            observed_at=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            fetched_at=datetime(
                2026,
                9,
                1,
                tzinfo=timezone.utc,
            ),
            is_estimated=True,
            estimation_method="estimated_from_prior_day",
            temporal_granularity="hourly",
            emission_factor_type="lifecycle",
            source_url="https://example.com",
        )

        insight = self.get(
            generate_insights(
                self.make_signals(
                    external_environment=environment,
                )
            ),
            InsightType.ENVIRONMENTAL_CONTEXT,
        )

        self.assertIn(
            "estimated",
            insight.message,
        )

        self.assertIn(
            "estimated_from_prior_day",
            insight.message,
        )

    def test_missing_external_environment_has_no_insight(self):
        insights = generate_insights(
            self.make_signals(
                external_environment=None,
            )
        )

        self.assertFalse(
            any(
                item.type
                == InsightType.ENVIRONMENTAL_CONTEXT
                for item in insights
            )
        )

    def test_action_priority_uses_existing_recommendation(self):
        recommendation = FakeUserRecommendation(
            recommendation=FakeRecommendation(
                title="Reduce unnecessary electricity usage",
            ),
            reason=(
                "Electricity is a major emission contributor."
            ),
            score=Decimal("90.0000"),
        )

        insight = self.get(
            generate_insights(
                self.make_signals(
                    recommendations=(recommendation,),
                )
            ),
            InsightType.ACTION_PRIORITY,
        )

        self.assertIn(
            "Reduce unnecessary electricity usage",
            insight.message,
        )

        self.assertIn(
            "Electricity is a major emission contributor",
            insight.message,
        )

    def test_action_priority_falls_back_to_top_category(self):
        insight = self.get(
            generate_insights(
                self.make_signals(
                    top_category="Transport",
                    top_category_emission=Decimal("60.0000"),
                )
            ),
            InsightType.ACTION_PRIORITY,
        )

        self.assertIn(
            "Transport",
            insight.message,
        )

    def test_no_fabricated_ml_insights(self):
        insights = generate_insights(
            self.make_signals()
        )

        types = {
            item.type
            for item in insights
        }

        self.assertNotIn(
            InsightType.PREDICTION,
            types,
        )

        self.assertNotIn(
            InsightType.SEGMENT,
            types,
        )

    def test_deterministic_output_order(self):
        signals = self.make_signals(
            top_category="Electricity",
            top_category_emission=Decimal("70.0000"),
            prediction=FakePrediction(
                predicted_emission=120.0,
                feature_period=date(
                    2026,
                    9,
                    1,
                ),
                target_period=date(
                    2026,
                    10,
                    1,
                ),
                model_version="rf-v1",
            ),
        )

        first = generate_insights(signals)
        second = generate_insights(signals)

        self.assertEqual(
            first,
            second,
        )

    def test_no_duplicate_insights(self):
        signals = self.make_signals(
            top_category="Electricity",
            top_category_emission=Decimal("70.0000"),
        )

        insights = generate_insights(signals)

        keys = [
            (
                item.type,
                item.title,
                item.message,
            )
            for item in insights
        ]

        self.assertEqual(
            len(keys),
            len(set(keys)),
        )