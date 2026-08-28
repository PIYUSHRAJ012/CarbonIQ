from decimal import Decimal

from django.test import SimpleTestCase

from carbon.services.emission_import.fuel import (
    IndiaFuelSourceAdapter,
)


class IndiaFuelSourceAdapterTests(SimpleTestCase):
    """
    Tests for the India-specific petrol and diesel
    emission-factor adapter.
    """

    def test_returns_petrol_factor(self):
        imported_factor = (
            IndiaFuelSourceAdapter
            .get_petrol_factor()
        )

        self.assertEqual(
            imported_factor.category_name,
            "Petrol",
        )

        self.assertEqual(
            imported_factor.factor,
            Decimal("2.37135"),
        )

        self.assertEqual(
            imported_factor.unit,
            "kgCO2/litre",
        )

        self.assertEqual(
            imported_factor.source_version,
            "CAFE 2027",
        )

        self.assertEqual(
            imported_factor.effective_from.year,
            2026,
        )

        self.assertEqual(
            imported_factor.effective_from.month,
            4,
        )

        self.assertEqual(
            imported_factor.effective_from.day,
            1,
        )

    def test_returns_diesel_factor(self):
        imported_factor = (
            IndiaFuelSourceAdapter
            .get_diesel_factor()
        )

        self.assertEqual(
            imported_factor.category_name,
            "Diesel",
        )

        self.assertEqual(
            imported_factor.factor,
            Decimal("2.64831"),
        )

        self.assertEqual(
            imported_factor.unit,
            "kgCO2/litre",
        )

        self.assertEqual(
            imported_factor.source_version,
            "CAFE 2027",
        )

        self.assertEqual(
            imported_factor.effective_from.year,
            2026,
        )

        self.assertEqual(
            imported_factor.effective_from.month,
            4,
        )

        self.assertEqual(
            imported_factor.effective_from.day,
            1,
        )

    def test_returns_all_fuel_factors(self):
        factors = (
            IndiaFuelSourceAdapter
            .get_factors()
        )

        self.assertEqual(
            len(factors),
            2,
        )

        self.assertEqual(
            {
                factor.category_name
                for factor in factors
            },
            {
                "Petrol",
                "Diesel",
            },
        )