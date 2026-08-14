from datetime import date
from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.emission import EmissionFactorService


class EmissionFactorServiceTests(TestCase):
    """
    Unit tests for the EmissionFactorService.
    """

    def setUp(self):
        self.category = ActivityCategory.objects.create(
            name="Test Electricity",
            description="Test category",
            unit="kWh",
            display_order=999,
            is_active=True,
        )

        self.factor = EmissionFactor.objects.create(
            activity_category=self.category,
            factor=Decimal("0.7080"),
            source="Test Source",
            effective_from=date(2026, 1, 1),
            effective_to=None,
            is_active=True,
        )

    def test_returns_active_factor(self):
        factor = EmissionFactorService.get_active_factor(
            self.category,
            date(2026, 8, 1),
        )

        self.assertEqual(factor, self.factor)

    def test_ignores_inactive_factor(self):
        self.factor.is_active = False
        self.factor.save()

        with self.assertRaises(ValidationError):
            EmissionFactorService.get_active_factor(
                self.category,
                date(2026, 8, 1),
            )

    def test_respects_effective_date_range(self):
        self.factor.effective_to = date(2026, 6, 30)
        self.factor.save()

        with self.assertRaises(ValidationError):
            EmissionFactorService.get_active_factor(
                self.category,
                date(2026, 7, 1),
            )

    def test_selects_most_recent_valid_factor(self):
        newer_factor = EmissionFactor.objects.create(
            activity_category=self.category,
            factor=Decimal("0.6500"),
            source="Newer Test Source",
            effective_from=date(2026, 7, 1),
            effective_to=None,
            is_active=True,
        )

        factor = EmissionFactorService.get_active_factor(
            self.category,
            date(2026, 8, 1),
        )

        self.assertEqual(factor, newer_factor)

    def test_raises_error_when_no_factor_exists(self):
        another_category = ActivityCategory.objects.create(
            name="No Factor Category",
            unit="unit",
            display_order=1000,
            is_active=True,
        )

        with self.assertRaises(ValidationError):
            EmissionFactorService.get_active_factor(
                another_category,
                date(2026, 8, 1),
            )