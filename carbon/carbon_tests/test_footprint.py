from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
    ActivityEntry,
)
from carbon.services.footprint import CarbonFootprintService


class CarbonFootprintServiceTests(TestCase):
    """
    Tests for the CarbonFootprintService.
    """

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="test@example.com",
            full_name="Test User",
            password="TestPassword123!",
        )

        self.electricity = ActivityCategory.objects.create(
            name="Test Electricity",
            description="Test electricity category",
            unit="kWh",
            display_order=999,
            is_active=True,
        )

        self.transportation = ActivityCategory.objects.create(
            name="Test Transportation",
            description="Test transportation category",
            unit="km",
            display_order=1000,
            is_active=True,
        )

        self.electricity_factor = EmissionFactor.objects.create(
            activity_category=self.electricity,
            factor=Decimal("0.7080"),
            source="Test Electricity Source",
            effective_from="2026-01-01",
            is_active=True,
        )

        self.transportation_factor = EmissionFactor.objects.create(
            activity_category=self.transportation,
            factor=Decimal("0.1210"),
            source="Test Transportation Source",
            effective_from="2026-01-01",
            is_active=True,
        )

    def create_activity_with_entries(self):
        activity = CarbonActivity.objects.create(
            user=self.user,
            notes="Test carbon activity",
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("250.00"),
            emission_factor_snapshot=Decimal("0.0000"),
            entry_emission=Decimal("0.0000"),
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.transportation,
            emission_factor=self.transportation_factor,
            quantity=Decimal("100.00"),
            emission_factor_snapshot=Decimal("0.0000"),
            entry_emission=Decimal("0.0000"),
        )

        return activity

    def test_calculates_and_creates_footprint(self):
        activity = self.create_activity_with_entries()

        footprint = CarbonFootprintService.calculate_footprint(activity)

        self.assertIsNotNone(footprint)

        self.assertEqual(
            footprint.total_emission,
            Decimal("189.1000"),
        )

        self.assertEqual(
            footprint.calculation_version,
            "v1.0",
        )

        activity.refresh_from_db()

        self.assertEqual(
            activity.status,
            CarbonActivity.Status.COMPLETED,
        )

    def test_stores_emission_factor_snapshots(self):
        activity = self.create_activity_with_entries()

        CarbonFootprintService.calculate_footprint(activity)

        entries = list(
            activity.entries.order_by("id")
        )

        self.assertEqual(
            entries[0].emission_factor_snapshot,
            Decimal("0.7080"),
        )

        self.assertEqual(
            entries[1].emission_factor_snapshot,
            Decimal("0.1210"),
        )

    def test_stores_entry_emissions(self):
        activity = self.create_activity_with_entries()

        CarbonFootprintService.calculate_footprint(activity)

        entries = list(
            activity.entries.order_by("id")
        )

        self.assertEqual(
            entries[0].entry_emission,
            Decimal("177.0000"),
        )

        self.assertEqual(
            entries[1].entry_emission,
            Decimal("12.1000"),
        )

    def test_recalculation_updates_existing_footprint(self):
        activity = self.create_activity_with_entries()

        first = CarbonFootprintService.calculate_footprint(activity)
        second = CarbonFootprintService.calculate_footprint(activity)

        self.assertEqual(first.id, second.id)

        self.assertEqual(
            CarbonFootprint.objects.filter(
                carbon_activity=activity
            ).count(),
            1,
        )

    def test_empty_activity_is_rejected(self):
        activity = CarbonActivity.objects.create(
            user=self.user,
            notes="Empty activity",
        )

        with self.assertRaises(ValidationError):
            CarbonFootprintService.calculate_footprint(activity)

        activity.refresh_from_db()

        self.assertEqual(
            activity.status,
            CarbonActivity.Status.PENDING,
        )

    def test_failure_marks_activity_as_failed(self):
        activity = CarbonActivity.objects.create(
            user=self.user,
            notes="Failure test",
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity=Decimal("250.00"),
            emission_factor_snapshot=Decimal("0.0000"),
            entry_emission=Decimal("0.0000"),
        )

        # Make the only applicable factor unavailable.
        self.electricity_factor.is_active = False
        self.electricity_factor.save()

        with self.assertRaises(ValidationError):
            CarbonFootprintService.calculate_footprint(activity)

        activity.refresh_from_db()

        self.assertEqual(
            activity.status,
            CarbonActivity.Status.FAILED,
        )

        self.assertFalse(
            CarbonFootprint.objects.filter(
                carbon_activity=activity
            ).exists()
        )