from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from carbon.models import BenchmarkScope, CarbonBenchmark, UserLocation


class ProfileLocationTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="profile-test@example.com",
            full_name="Profile Test User",
            password="TestPassword123!",
        )

        CarbonBenchmark.objects.create(
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

    def setUp(self):
        self.client.force_login(self.user)

    def test_profile_requires_login(self):
        self.client.logout()

        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 302)

    def test_profile_loads_without_existing_location(self):
        response = self.client.get(reverse("accounts:profile"))

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Benchmarking Location")
        self.assertContains(response, "Select your state")
        self.assertContains(response, "Select your district")

        self.assertFalse(
            UserLocation.objects.filter(user=self.user).exists()
        )

    def test_profile_saves_valid_location(self):
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "state": "KARNATAKA",
                "district": "Mysore",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:profile"),
        )

        location = UserLocation.objects.get(user=self.user)

        self.assertEqual(location.state, "KARNATAKA")
        self.assertEqual(location.district, "Mysore")

    def test_profile_rejects_invalid_location_pair(self):
        response = self.client.post(
            reverse("accounts:profile"),
            {
                "state": "KARNATAKA",
                "district": "Nonexistent Test District",
            },
        )

        self.assertEqual(response.status_code, 200)

        self.assertContains(
            response,
            "Select a valid choice.",
        )

        self.assertFalse(
            UserLocation.objects.filter(user=self.user).exists()
        )

    def test_existing_location_is_updated(self):
        UserLocation.objects.create(
            user=self.user,
            state="KARNATAKA",
            district="Mysore",
        )

        response = self.client.post(
            reverse("accounts:profile"),
            {
                "state": "KARNATAKA",
                "district": "Mysore",
            },
        )

        self.assertRedirects(
            response,
            reverse("accounts:profile"),
        )

        self.assertEqual(
            UserLocation.objects.filter(user=self.user).count(),
            1,
        )

        location = UserLocation.objects.get(user=self.user)

        self.assertEqual(location.state, "KARNATAKA")
        self.assertEqual(location.district, "Mysore")