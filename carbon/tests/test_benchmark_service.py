from django.contrib.auth import get_user_model
from django.test import TestCase

from carbon.models import BenchmarkScope, CarbonBenchmark, UserLocation
from carbon.services.benchmark import resolve_benchmark


User = get_user_model()


class BenchmarkResolutionServiceTests(TestCase):

    @classmethod
    def setUpTestData(cls):
        cls.user = User.objects.create_user(
            email="benchmark-test@example.com",
            full_name="Benchmark Test User",
            password="TestPassword123!",
        )

        cls.district_benchmark = CarbonBenchmark.objects.create(
            scope=BenchmarkScope.DISTRICT,
            state="KARNATAKA",
            district="Mysore",
            reference_period="2011-2012",
            value="0.613",
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
            value="0.560",
            unit="tCO2/person/year",
            population_basis="per_capita",
            source="Test Source",
            source_reference="test://benchmark",
            methodology="Test methodology",
            is_active=True,
        )

    def test_resolves_district_benchmark(self):
        UserLocation.objects.create(
            user=self.user,
            state="Karnataka",
            district="Mysore",
        )

        result = resolve_benchmark(self.user)

        self.assertEqual(
            result.benchmark.pk,
            self.district_benchmark.pk,
        )
        self.assertEqual(result.scope, BenchmarkScope.DISTRICT)
        self.assertFalse(result.used_fallback)

    def test_resolves_district_case_and_whitespace_insensitively(self):
        UserLocation.objects.create(
            user=self.user,
            state="  karnataka  ",
            district="  MYSORE ",
        )

        result = resolve_benchmark(self.user)

        self.assertEqual(
            result.benchmark.pk,
            self.district_benchmark.pk,
        )
        self.assertEqual(result.scope, BenchmarkScope.DISTRICT)
        self.assertFalse(result.used_fallback)

    def test_falls_back_to_national_benchmark(self):
        UserLocation.objects.create(
            user=self.user,
            state="Karnataka",
            district="Unknown District",
        )

        result = resolve_benchmark(self.user)

        self.assertEqual(
            result.benchmark.pk,
            self.national_benchmark.pk,
        )
        self.assertEqual(result.scope, BenchmarkScope.NATIONAL)
        self.assertTrue(result.used_fallback)

    def test_raises_when_user_location_is_missing(self):
        with self.assertRaisesMessage(
            ValueError,
            "User location is not configured.",
        ):
            resolve_benchmark(self.user)

    def test_raises_when_no_national_benchmark_exists(self):
        self.national_benchmark.delete()

        UserLocation.objects.create(
            user=self.user,
            state="Karnataka",
            district="Unknown District",
        )

        with self.assertRaisesMessage(
            ValueError,
            "No active national carbon benchmark is available.",
        ):
            resolve_benchmark(self.user)