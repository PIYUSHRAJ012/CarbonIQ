from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from carbon.models import (
    BenchmarkScope,
    CarbonActivity,
    CarbonBenchmark,
    CarbonFootprint,
    UserLocation,
)
from carbon.services.comparison import (
    benchmark_monthly_kg,
    get_user_monthly_benchmark_comparison,
)


User = get_user_model()


class BenchmarkComparisonServiceTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="comparison-test@example.com",
            full_name="Comparison Test User",
            password="TestPassword123!",
        )

        UserLocation.objects.create(
            user=cls.user,
            state="KARNATAKA",
            district="Mysore",
        )

        cls.district_benchmark = CarbonBenchmark.objects.create(
            scope=BenchmarkScope.DISTRICT,
            state="KARNATAKA",
            district="Mysore",
            reference_period="2011-2012",
            value=Decimal("0.613"),
            unit="tCO2/person/year",
            population_basis="per_capita",
            source="Test Source",
            source_reference="test://benchmark",
            methodology="Test methodology",
            is_active=True,
        )

        cls.national_benchmark = CarbonBenchmark.objects.create(
            scope=BenchmarkScope.NATIONAL,
            reference_period="2011-2012",
            value=Decimal("0.560"),
            unit="tCO2/person/year",
            population_basis="per_capita",
            source="Test Source",
            source_reference="test://benchmark",
            methodology="Test methodology",
            is_active=True,
        )

    def _create_completed_footprint(
        self,
        total_emission,
        calculated_at,
    ):
        activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
            notes="Comparison test activity",
        )

        footprint = CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal(str(total_emission)),
            calculated_at=calculated_at,
            calculation_version="v1.0",
        )

        return footprint

    def test_benchmark_monthly_conversion(self):
        result = benchmark_monthly_kg(Decimal("0.613"))

        expected = (
            Decimal("0.613")
            * Decimal("1000")
            / Decimal("12")
        )

        self.assertEqual(result, expected)

    def test_monthly_emissions_are_aggregated(self):
        timestamp = timezone.datetime(
            2026,
            8,
            10,
            tzinfo=timezone.get_current_timezone(),
        )

        self._create_completed_footprint("10.0000", timestamp)
        self._create_completed_footprint("5.0000", timestamp)

        result = get_user_monthly_benchmark_comparison(self.user)

        self.assertEqual(len(result.personal_monthly_comparisons), 1)

        comparison = result.personal_monthly_comparisons[0]

        self.assertEqual(
            comparison.personal_emission_kg,
            Decimal("15.0000"),
        )

    def test_completed_only_are_included(self):
        timestamp = timezone.datetime(
            2026,
            8,
            10,
            tzinfo=timezone.get_current_timezone(),
        )

        self._create_completed_footprint("10.0000", timestamp)

        activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.FAILED,
            notes="Failed test activity",
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("100.0000"),
            calculated_at=timestamp,
            calculation_version="v1.0",
        )

        result = get_user_monthly_benchmark_comparison(self.user)

        comparison = result.personal_monthly_comparisons[0]

        self.assertEqual(
            comparison.personal_emission_kg,
            Decimal("10.0000"),
        )

    def test_comparison_against_district_benchmark(self):
        timestamp = timezone.datetime(
            2026,
            8,
            10,
            tzinfo=timezone.get_current_timezone(),
        )

        self._create_completed_footprint("100.0000", timestamp)

        result = get_user_monthly_benchmark_comparison(self.user)

        self.assertEqual(
            result.benchmark_resolution.scope,
            BenchmarkScope.DISTRICT,
        )

        self.assertFalse(
            result.benchmark_resolution.used_fallback,
        )

        comparison = result.personal_monthly_comparisons[0]

        self.assertEqual(
            comparison.benchmark_emission_kg,
            Decimal("0.613")
            * Decimal("1000")
            / Decimal("12"),
        )

        self.assertFalse(comparison.below_benchmark)
        self.assertGreater(comparison.difference_percent, Decimal("0"))

    def test_empty_history_returns_no_monthly_comparisons(self):
        result = get_user_monthly_benchmark_comparison(self.user)

        self.assertEqual(
            result.personal_monthly_comparisons,
            (),
        )