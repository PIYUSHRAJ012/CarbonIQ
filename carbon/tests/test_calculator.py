from decimal import Decimal

from django.core.exceptions import ValidationError
from django.test import TestCase

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.calculator import CarbonCalculationService


class CarbonCalculationServiceTests(TestCase):
    """
    Unit tests for the CarbonCalculationService.
    """

    def setUp(self):
        self.category = ActivityCategory.objects.create(
            name="Test Transportation",
            description="Test category",
            unit="km",
            display_order=999,
            is_active=True,
        )

        self.factor = EmissionFactor.objects.create(
            activity_category=self.category,
            factor=Decimal("0.1210"),
            source="Test Source",
            effective_from="2026-01-01",
            is_active=True,
        )

    def test_calculates_emission_correctly(self):
        result = CarbonCalculationService.calculate_emission(
            quantity=Decimal("100.00"),
            emission_factor=self.factor,
        )

        self.assertEqual(result, Decimal("12.1000"))

    def test_calculates_decimal_values_correctly(self):
        result = CarbonCalculationService.calculate_emission(
            quantity=Decimal("100.50"),
            emission_factor=self.factor,
        )

        self.assertEqual(result, Decimal("12.1605"))

    def test_zero_quantity_returns_zero(self):
        result = CarbonCalculationService.calculate_emission(
            quantity=Decimal("0.00"),
            emission_factor=self.factor,
        )

        self.assertEqual(result, Decimal("0.0000"))

    def test_negative_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            CarbonCalculationService.calculate_emission(
                quantity=Decimal("-10.00"),
                emission_factor=self.factor,
            )

    def test_missing_quantity_is_rejected(self):
        with self.assertRaises(ValidationError):
            CarbonCalculationService.calculate_emission(
                quantity=None,
                emission_factor=self.factor,
            )

    def test_invalid_emission_factor_is_rejected(self):
        with self.assertRaises(ValidationError):
            CarbonCalculationService.calculate_emission(
                quantity=Decimal("100.00"),
                emission_factor="invalid-factor",
            )

    def test_non_decimal_quantity_is_converted_safely(self):
        result = CarbonCalculationService.calculate_emission(
            quantity="100.50",
            emission_factor=self.factor,
        )

        self.assertEqual(result, Decimal("12.1605"))