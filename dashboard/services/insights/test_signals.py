from datetime import timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from carbon.models import UserLocation
from external_data.models import ExternalEnvironmentalObservation
from ml.services.prediction import PredictionServiceError
from ml.services.segmentation import SegmentationPredictionError
from ml.services.segmentation_profile import UserSegmentProfileError
from recommendations.models import (
    OffsetProject,
    OffsetRecommendation,
    Recommendation,
    UserRecommendation,
)

from dashboard.services.insights.signals import (
    ExternalEnvironmentSignal,
    InsightSignalError,
    build_insight_signals,
)


class InsightSignalServiceTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="insights@example.com",
            full_name="Insights Test User",
            password="TestPassword123!",
        )
        self.other_user = CustomUser.objects.create_user(
            email="other-insights@example.com",
            full_name="Other Insights Test User",
            password="TestPassword123!",
        )
        self._recommendation_count = 0
        self._offset_project_count = 0

    def build_signals(
        self,
        *,
        total=Decimal("0.0000"),
        monthly=(),
        weekly=(),
        categories=(),
        prediction=None,
        prediction_error=None,
        segment=None,
        segment_error=None,
        benchmark=None,
        benchmark_error=None,
    ):
        """Build signals with deterministic service-layer dependencies."""
        with patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_total_emission",
            return_value=total,
        ) as total_emission, patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_monthly_emissions",
            return_value=monthly,
        ) as monthly_emissions, patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_weekly_emissions",
            return_value=weekly,
        ) as weekly_emissions, patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_category_emissions",
            return_value=categories,
        ) as category_emissions, patch(
            "dashboard.services.insights.signals.predict_next_month_carbon",
            return_value=prediction,
        ) as prediction_service, patch(
            "dashboard.services.insights.signals.get_user_segment_profile",
            return_value=segment,
        ) as segment_service, patch(
            "dashboard.services.insights.signals."
            "get_user_monthly_benchmark_comparison",
            return_value=benchmark,
        ) as benchmark_service:
            if prediction_error is not None:
                prediction_service.side_effect = prediction_error

            if segment_error is not None:
                segment_service.side_effect = segment_error

            if benchmark_error is not None:
                benchmark_service.side_effect = benchmark_error

            signals = build_insight_signals(self.user)

        total_emission.assert_called_once_with(self.user)
        monthly_emissions.assert_called_once_with(self.user)
        weekly_emissions.assert_called_once_with(self.user)
        category_emissions.assert_called_once_with(self.user)

        return signals

    def create_catalog_recommendation(self, title):
        self._recommendation_count += 1

        return Recommendation.objects.create(
            title=title,
            description=f"Test description for {title}.",
            priority=50 + self._recommendation_count,
        )

    def create_user_recommendation(
        self,
        *,
        user=None,
        status=UserRecommendation.Status.ACTIVE,
        score=Decimal("50.0000"),
    ):
        user = user or self.user
        recommendation = self.create_catalog_recommendation(
            f"Recommendation {self._recommendation_count + 1}"
        )

        return UserRecommendation.objects.create(
            user=user,
            recommendation=recommendation,
            score=score,
            reason="Persisted recommendation for insight-signal testing.",
            status=status,
        )

    def create_offset_project(self):
        self._offset_project_count += 1
        project_number = self._offset_project_count

        return OffsetProject.objects.create(
            name=f"Offset Project {project_number}",
            registry="Test Registry",
            registry_project_id=f"TEST-OFFSET-{project_number}",
            registry_url=f"https://example.com/projects/{project_number}",
            source_last_verified_at=timezone.now(),
        )

    def create_offset_recommendation(
        self,
        *,
        user=None,
        status=OffsetRecommendation.Status.ACTIVE,
        score=Decimal("50.0000"),
    ):
        user = user or self.user

        return OffsetRecommendation.objects.create(
            user=user,
            offset_project=self.create_offset_project(),
            score=score,
            reason="Persisted offset recommendation for insight testing.",
            indicative_tonnes=Decimal("1.2500"),
            status=status,
        )

    def create_observation(self, **overrides):
        observed_at = overrides.pop("observed_at", timezone.now())
        values = {
            "provider": "test-provider",
            "data_type": (
                ExternalEnvironmentalObservation.DataType.GRID_CARBON_INTENSITY
            ),
            "zone": "Karnataka",
            "value": Decimal("335.3200"),
            "unit": "gCO2e/kWh",
            "observed_at": observed_at,
            "fetched_at": observed_at,
            "is_estimated": False,
            "estimation_method": "",
            "temporal_granularity": (
                ExternalEnvironmentalObservation.TemporalGranularity.HOURLY
            ),
            "emission_factor_type": (
                ExternalEnvironmentalObservation.EmissionFactorType.LIFECYCLE
            ),
            "flow_traced": False,
            "source_url": "https://example.com/grid-carbon-intensity",
        }
        values.update(overrides)

        return ExternalEnvironmentalObservation.objects.create(**values)

    def test_analytics_signals_are_populated_correctly(self):
        monthly = [{"month": "2026-08", "total_emission": Decimal("40.0000")}]
        weekly = [{"week": "2026-W35", "total_emission": Decimal("10.0000")}]
        categories = [
            {
                "category__name": "Electricity",
                "total_emission": Decimal("70.0000"),
            },
            {
                "category__name": "Transport",
                "total_emission": Decimal("30.0000"),
            },
        ]

        signals = self.build_signals(
            total=Decimal("100.0000"),
            monthly=monthly,
            weekly=weekly,
            categories=categories,
        )

        self.assertEqual(signals.current_total_emission, Decimal("100.0000"))
        self.assertEqual(signals.monthly_emissions, tuple(monthly))
        self.assertEqual(signals.weekly_emissions, tuple(weekly))
        self.assertEqual(signals.category_emissions, tuple(categories))
        self.assertEqual(signals.top_category, "Electricity")
        self.assertEqual(signals.top_category_emission, Decimal("70.0000"))

    def test_empty_analytics_returns_valid_empty_tuples(self):
        signals = self.build_signals(
            total=Decimal("0.0000"),
            monthly=(),
            weekly=(),
            categories=(),
        )

        self.assertEqual(signals.current_total_emission, Decimal("0.0000"))
        self.assertEqual(signals.monthly_emissions, ())
        self.assertEqual(signals.weekly_emissions, ())
        self.assertEqual(signals.category_emissions, ())
        self.assertIsNone(signals.top_category)
        self.assertIsNone(signals.top_category_emission)

    def test_top_category_is_derived_from_first_ordered_category(self):
        categories = [
            {
                "category__name": "Transport",
                "total_emission": Decimal("180.0000"),
            },
            {
                "category__name": "Electricity",
                "total_emission": Decimal("70.0000"),
            },
        ]

        signals = self.build_signals(categories=categories)

        self.assertEqual(signals.top_category, "Transport")
        self.assertEqual(signals.top_category_emission, Decimal("180.0000"))

    def test_prediction_is_populated_when_available(self):
        prediction = object()

        signals = self.build_signals(prediction=prediction)

        self.assertIs(signals.prediction, prediction)

    def test_prediction_service_error_results_in_none(self):
        signals = self.build_signals(
            prediction_error=PredictionServiceError("Model unavailable."),
        )

        self.assertIsNone(signals.prediction)

    def test_user_segment_is_populated_when_available(self):
        segment = object()

        signals = self.build_signals(segment=segment)

        self.assertIs(signals.user_segment, segment)

    def test_segmentation_readiness_errors_result_in_none(self):
        for error in (
            UserSegmentProfileError("Profile unavailable."),
            SegmentationPredictionError("Prediction unavailable."),
        ):
            with self.subTest(error=type(error).__name__):
                signals = self.build_signals(segment_error=error)

                self.assertIsNone(signals.user_segment)

    def test_active_user_recommendations_are_included_and_sorted(self):
        lower_score = self.create_user_recommendation(score=Decimal("50.0000"))
        higher_score = self.create_user_recommendation(score=Decimal("90.0000"))
        self.create_user_recommendation(
            user=self.other_user,
            score=Decimal("99.0000"),
        )

        signals = self.build_signals()

        self.assertEqual(
            signals.recommendations,
            (higher_score, lower_score),
        )

    def test_non_active_user_recommendations_are_excluded(self):
        active = self.create_user_recommendation()

        for status in (
            UserRecommendation.Status.DISMISSED,
            UserRecommendation.Status.COMPLETED,
            UserRecommendation.Status.SUPERSEDED,
        ):
            self.create_user_recommendation(status=status)

        signals = self.build_signals()

        self.assertEqual(signals.recommendations, (active,))

    def test_active_offset_recommendations_are_included_and_sorted(self):
        lower_score = self.create_offset_recommendation(score=Decimal("50.0000"))
        higher_score = self.create_offset_recommendation(score=Decimal("90.0000"))
        self.create_offset_recommendation(
            user=self.other_user,
            score=Decimal("99.0000"),
        )

        signals = self.build_signals()

        self.assertEqual(
            signals.offset_context,
            (higher_score, lower_score),
        )

    def test_non_active_offset_recommendations_are_excluded(self):
        active = self.create_offset_recommendation()

        for status in (
            OffsetRecommendation.Status.DISMISSED,
            OffsetRecommendation.Status.COMPLETED,
            OffsetRecommendation.Status.SUPERSEDED,
        ):
            self.create_offset_recommendation(status=status)

        signals = self.build_signals()

        self.assertEqual(signals.offset_context, (active,))

    def test_benchmark_is_included_when_available(self):
        benchmark = object()

        signals = self.build_signals(benchmark=benchmark)

        self.assertIs(signals.benchmark, benchmark)

    def test_missing_benchmark_or_location_is_optional(self):
        signals = self.build_signals(
            benchmark_error=ValueError("No benchmark is configured."),
        )

        self.assertIsNone(signals.benchmark)
        self.assertIsNone(signals.external_environment)

    def test_latest_matching_e6_observation_is_selected(self):
        UserLocation.objects.create(
            user=self.user,
            state=" Karnataka ",
            district="Bengaluru Urban",
        )
        now = timezone.now()
        self.create_observation(
            zone="Karnataka",
            value=Decimal("300.0000"),
            observed_at=now - timedelta(hours=2),
            fetched_at=now - timedelta(hours=1),
        )
        latest = self.create_observation(
            zone="karnataka",
            value=Decimal("325.5000"),
            observed_at=now - timedelta(hours=1),
            fetched_at=now,
            is_estimated=True,
            estimation_method="estimated_from_prior_day",
            source_url="https://example.com/latest-grid-carbon-intensity",
        )

        signals = self.build_signals()

        external_environment = signals.external_environment
        self.assertIsInstance(external_environment, ExternalEnvironmentSignal)
        self.assertEqual(external_environment.provider, latest.provider)
        self.assertEqual(external_environment.zone, latest.zone)
        self.assertEqual(external_environment.value, Decimal("325.5000"))
        self.assertEqual(external_environment.unit, latest.unit)
        self.assertEqual(external_environment.observed_at, latest.observed_at)
        self.assertEqual(external_environment.fetched_at, latest.fetched_at)
        self.assertTrue(external_environment.is_estimated)
        self.assertEqual(
            external_environment.estimation_method,
            "estimated_from_prior_day",
        )
        self.assertEqual(
            external_environment.temporal_granularity,
            ExternalEnvironmentalObservation.TemporalGranularity.HOURLY,
        )
        self.assertEqual(
            external_environment.emission_factor_type,
            ExternalEnvironmentalObservation.EmissionFactorType.LIFECYCLE,
        )
        self.assertEqual(external_environment.source_url, latest.source_url)

    def test_missing_e6_observation_results_in_none(self):
        UserLocation.objects.create(
            user=self.user,
            state="Karnataka",
            district="Bengaluru Urban",
        )

        signals = self.build_signals()

        self.assertIsNone(signals.external_environment)

    def test_e6_observation_from_another_state_is_never_used(self):
        UserLocation.objects.create(
            user=self.user,
            state="Karnataka",
            district="Bengaluru Urban",
        )
        self.create_observation(
            zone="Maharashtra",
            value=Decimal("421.7500"),
        )

        signals = self.build_signals()

        self.assertIsNone(signals.external_environment)

    def test_all_returned_collections_are_tuples(self):
        signals = self.build_signals(
            monthly=[{"month": "2026-08", "total_emission": Decimal("10.0000")}],
            weekly=[{"week": "2026-W35", "total_emission": Decimal("10.0000")}],
            categories=[
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("10.0000"),
                }
            ],
        )

        self.assertIsInstance(signals.monthly_emissions, tuple)
        self.assertIsInstance(signals.weekly_emissions, tuple)
        self.assertIsInstance(signals.category_emissions, tuple)
        self.assertIsInstance(signals.recommendations, tuple)
        self.assertIsInstance(signals.offset_context, tuple)

    def test_unexpected_analytics_failure_raises_insight_signal_error(self):
        with patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_monthly_emissions",
            return_value=(),
        ), patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_weekly_emissions",
            return_value=(),
        ), patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_category_emissions",
            return_value=(),
        ), patch(
            "dashboard.services.insights.signals."
            "AnalyticsAggregationService.get_total_emission",
            side_effect=RuntimeError("Database failure."),
        ):
            with self.assertRaises(InsightSignalError) as raised:
                build_insight_signals(self.user)

        self.assertIsInstance(raised.exception.__cause__, RuntimeError)
