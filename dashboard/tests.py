from decimal import Decimal

from django.test import TestCase

from django.urls import reverse

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
)

from dashboard.services.dashboard import DashboardService


class DashboardServiceTests(TestCase):
    """
    Tests for dashboard data composition.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="dashboard@example.com",
            full_name="Dashboard User",
            password="TestPassword123!",
        )

    def test_dashboard_returns_empty_data_for_new_user(self):
        data = DashboardService.get_dashboard_data(self.user)

        self.assertEqual(
            data["total_emission"],
            Decimal("0.0000"),
        )

        self.assertEqual(
            data["monthly_emissions"],
            [],
        )

        self.assertEqual(
            data["weekly_emissions"],
            [],
        )

        self.assertEqual(
            data["category_emissions"],
            [],
        )

    def test_dashboard_returns_aggregated_data(self):
        category = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        factor = EmissionFactor.objects.create(
            activity_category=category,
            factor=Decimal("1.250000"),
            source="Test source",
            effective_from="2026-01-01",
            is_active=True,
        )

        activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=category,
            emission_factor=factor,
            quantity=10,
            entry_emission=Decimal("12.5000"),
            emission_factor_snapshot=Decimal("1.250000"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("12.5000"),
            calculation_version="v1.0",
        )

        data = DashboardService.get_dashboard_data(self.user)

        self.assertEqual(
            data["total_emission"],
            Decimal("12.5000"),
        )

        self.assertEqual(
            len(data["category_emissions"]),
            1,
        )

        self.assertEqual(
            data["category_emissions"][0]["category__name"],
            "Electricity",
        )

        self.assertEqual(
            data["category_emissions"][0]["total_emission"],
            Decimal("12.5000"),
        )

    def test_dashboard_contains_chart_data(self):
        data = DashboardService.get_dashboard_data(self.user)

        self.assertIn("monthly_chart_data", data)
        self.assertIn("weekly_chart_data", data)
        self.assertIn("category_chart_data", data)

        self.assertEqual(
            data["monthly_chart_data"],
            [],
        )

        self.assertEqual(
            data["weekly_chart_data"],
            [],
        )

        self.assertEqual(
            data["category_chart_data"],
            [],
        )

class DashboardViewTests(TestCase):
    """
    Tests for the dashboard HTTP layer.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="dashboardview@example.com",
            full_name="Dashboard View User",
            password="TestPassword123!",
        )

    def test_dashboard_requires_login(self):
        response = self.client.get(
            reverse("dashboard:home")
        )

        self.assertEqual(response.status_code, 302)

    def test_authenticated_user_can_access_dashboard(self):
        self.client.force_login(self.user)

        response = self.client.get(
            reverse("dashboard:home")
        )

        self.assertEqual(response.status_code, 200)