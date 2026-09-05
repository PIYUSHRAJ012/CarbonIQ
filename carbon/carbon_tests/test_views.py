from decimal import Decimal

from django.test import TestCase
from django.urls import reverse

from accounts.models import CustomUser
from carbon.models import ActivityCategory, CarbonActivity, CarbonFootprint


class CarbonResultViewTests(TestCase):
    """
    Tests for the CarbonIQ carbon result page.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="user1@test.com",
            full_name="User One",
            password="TestPassword123!",
        )

        cls.other_user = CustomUser.objects.create_user(
            email="user2@test.com",
            full_name="User Two",
            password="TestPassword123!",
        )

        cls.category = ActivityCategory.objects.create(
            name="Test Electricity",
            description="Test electricity category",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

    def setUp(self):
        self.activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        self.footprint = CarbonFootprint.objects.create(
            carbon_activity=self.activity,
            total_emission=Decimal("76.8500"),
            calculation_version="v1.0",
        )

    def test_authenticated_owner_can_view_result(self):
        self.client.login(
            email="user1@test.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "carbon:result",
                kwargs={"pk": self.activity.pk},
            )
        )

        self.assertEqual(response.status_code, 200)

        self.assertTemplateUsed(
            response,
            "carbon/result.html",
        )

        self.assertEqual(
            response.context["footprint"],
            self.footprint,
        )

    def test_user_cannot_view_another_users_result(self):
        self.client.login(
            email="user2@test.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "carbon:result",
                kwargs={"pk": self.activity.pk},
            )
        )

        self.assertEqual(response.status_code, 404)

    def test_anonymous_user_is_redirected_to_login(self):
        response = self.client.get(
            reverse(
                "carbon:result",
                kwargs={"pk": self.activity.pk},
            )
        )

        self.assertEqual(response.status_code, 302)

        self.assertIn(
            "/accounts/login/",
            response.url,
        )

    def test_result_contains_total_emission(self):
        self.client.login(
            email="user1@test.com",
            password="TestPassword123!",
        )

        response = self.client.get(
            reverse(
                "carbon:result",
                kwargs={"pk": self.activity.pk},
            )
        )

        self.assertContains(
            response,
            "76.85",
        )