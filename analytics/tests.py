from decimal import Decimal

from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
)

from analytics.services.aggregation import AnalyticsAggregationService

from datetime import datetime
from django.utils import timezone

class AnalyticsAggregationServiceTests(TestCase):
    """
    Tests for reusable analytics aggregation operations.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="analytics@example.com",
            full_name="Analytics User",
            password="TestPassword123!",
        )

        self.other_user = CustomUser.objects.create_user(
            email="other@example.com",
            full_name="Other User",
            password="TestPassword123!",
        )

    def create_footprint(
        self,
        user,
        total_emission,
        status=CarbonActivity.Status.COMPLETED,
        calculated_at=None,
    ):
        activity = CarbonActivity.objects.create(
            user=user,
            status=status,
        )

        footprint = CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal(total_emission),
            calculation_version="v1.0",
        )

        if calculated_at is not None:
            CarbonFootprint.objects.filter(pk=footprint.pk).update(
                calculated_at=calculated_at
            )
            footprint.refresh_from_db()

        return footprint

    def test_total_emission_for_user(self):
        self.create_footprint(self.user, "12.5000")
        self.create_footprint(self.user, "7.2500")

        total = AnalyticsAggregationService.get_total_emission(
            self.user
        )

        self.assertEqual(
            total,
            Decimal("19.7500"),
        )

    def test_failed_activities_are_excluded(self):
        self.create_footprint(
            self.user,
            "12.5000",
            status=CarbonActivity.Status.FAILED,
        )

        total = AnalyticsAggregationService.get_total_emission(
            self.user
        )

        self.assertEqual(
            total,
            Decimal("0.0000"),
        )

    def test_other_users_data_is_excluded(self):
        self.create_footprint(self.user, "10.0000")
        self.create_footprint(self.other_user, "50.0000")

        total = AnalyticsAggregationService.get_total_emission(
            self.user
        )

        self.assertEqual(
            total,
            Decimal("10.0000"),
        )

    def test_zero_when_user_has_no_footprints(self):
        total = AnalyticsAggregationService.get_total_emission(
            self.user
        )

        self.assertEqual(
            total,
            Decimal("0.0000"),
        )

    def test_monthly_emissions(self):
        january_1 = timezone.make_aware(
            datetime(2026, 1, 5, 10, 0)
        )
        january_2 = timezone.make_aware(
            datetime(2026, 1, 20, 10, 0)
        )
        february = timezone.make_aware(
            datetime(2026, 2, 10, 10, 0)
        )

        self.create_footprint(
            self.user,
            "10.0000",
            calculated_at=january_1,
        )
        self.create_footprint(
            self.user,
            "5.0000",
            calculated_at=january_2,
        )
        self.create_footprint(
            self.user,
            "8.0000",
            calculated_at=february,
        )

        result = list(
            AnalyticsAggregationService.get_monthly_emissions(
                self.user
            )
        )

        self.assertEqual(len(result), 2)

        self.assertEqual(
            result[0]["total_emission"],
            Decimal("15.0000"),
        )

        self.assertEqual(
            result[1]["total_emission"],
            Decimal("8.0000"),
        )

    def test_weekly_emissions(self):
        monday = timezone.make_aware(
            datetime(2026, 2, 2, 10, 0)
        )
        wednesday = timezone.make_aware(
            datetime(2026, 2, 4, 10, 0)
        )
        next_week = timezone.make_aware(
            datetime(2026, 2, 9, 10, 0)
        )

        self.create_footprint(
            self.user,
            "10.0000",
            calculated_at=monday,
        )
        self.create_footprint(
            self.user,
            "5.0000",
            calculated_at=wednesday,
        )
        self.create_footprint(
            self.user,
            "8.0000",
            calculated_at=next_week,
        )

        result = list(
            AnalyticsAggregationService.get_weekly_emissions(
                self.user
            )
        )

        self.assertEqual(len(result), 2)

        self.assertEqual(
            result[0]["total_emission"],
            Decimal("15.0000"),
        )

        self.assertEqual(
            result[1]["total_emission"],
            Decimal("8.0000"),
        )

    def test_category_emissions(self):
        electricity = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        transport = ActivityCategory.objects.create(
            name="Transportation",
            description="Transportation activity",
            unit="km",
            display_order=2,
            is_active=True,
        )

        electricity_factor = EmissionFactor.objects.create(
            activity_category=electricity,
            factor=Decimal("1.250000"),
            source="Test source",
            effective_from=datetime(2026, 1, 1).date(),
            is_active=True,
        )

        transport_factor = EmissionFactor.objects.create(
            activity_category=transport,
            factor=Decimal("0.400000"),
            source="Test source",
            effective_from=datetime(2026, 1, 1).date(),
            is_active=True,
        )

        first_activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=first_activity,
            category=electricity,
            emission_factor=electricity_factor,
            quantity=10,
            entry_emission=Decimal("12.5000"),
            emission_factor_snapshot=Decimal("1.250000"),
        )

        ActivityEntry.objects.create(
            carbon_activity=first_activity,
            category=transport,
            emission_factor=transport_factor,
            quantity=20,
            entry_emission=Decimal("8.0000"),
            emission_factor_snapshot=Decimal("0.400000"),
        )

        second_activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=second_activity,
            category=electricity,
            emission_factor=electricity_factor,
            quantity=5,
            entry_emission=Decimal("6.5000"),
            emission_factor_snapshot=Decimal("1.300000"),
        )

        result = list(
            AnalyticsAggregationService.get_category_emissions(
                self.user
            )
        )

        self.assertEqual(len(result), 2)

        self.assertEqual(
            result[0]["category__name"],
            "Electricity",
        )

        self.assertEqual(
            result[0]["total_emission"],
            Decimal("19.0000"),
        )

        self.assertEqual(
            result[1]["category__name"],
            "Transportation",
        )

        self.assertEqual(
            result[1]["total_emission"],
            Decimal("8.0000"),
        )

    def test_category_emissions_exclude_failed_activities(self):
        electricity = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        electricity_factor = EmissionFactor.objects.create(
            activity_category=electricity,
            factor=Decimal("1.250000"),
            source="Test source",
            effective_from=datetime(2026, 1, 1).date(),
            is_active=True,
        )

        failed_activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.FAILED,
        )

        ActivityEntry.objects.create(
            carbon_activity=failed_activity,
            category=electricity,
            emission_factor=electricity_factor,
            quantity=10,
            entry_emission=Decimal("12.5000"),
            emission_factor_snapshot=Decimal("1.250000"),
        )

        result = list(
            AnalyticsAggregationService.get_category_emissions(
                self.user
            )
        )

        self.assertEqual(result, [])

    def test_category_emissions_exclude_other_users(self):
        electricity = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        electricity_factor = EmissionFactor.objects.create(
            activity_category=electricity,
            factor=Decimal("1.250000"),
            source="Test source",
            effective_from=datetime(2026, 1, 1).date(),
            is_active=True,
        )

        user_activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=user_activity,
            category=electricity,
            emission_factor=electricity_factor,
            quantity=10,
            entry_emission=Decimal("12.5000"),
            emission_factor_snapshot=Decimal("1.250000"),
        )

        other_user_activity = CarbonActivity.objects.create(
            user=self.other_user,
            status=CarbonActivity.Status.COMPLETED,
        )

        ActivityEntry.objects.create(
            carbon_activity=other_user_activity,
            category=electricity,
            emission_factor=electricity_factor,
            quantity=100,
            entry_emission=Decimal("125.0000"),
            emission_factor_snapshot=Decimal("1.250000"),
        )

        result = list(
            AnalyticsAggregationService.get_category_emissions(
                self.user
            )
        )

        self.assertEqual(len(result), 1)

        self.assertEqual(
            result[0]["category__name"],
            "Electricity",
        )

        self.assertEqual(
            result[0]["total_emission"],
            Decimal("12.5000"),
        )

    