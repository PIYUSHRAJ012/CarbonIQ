from decimal import Decimal

from django.test import SimpleTestCase

from carbon.services.emission_import.shopping import (
    IndiaShoppingSourceAdapter,
)


class IndiaShoppingSourceAdapterTests(SimpleTestCase):
    """
    Tests for the India-specific shopping emission-factor adapter.
    """

    def test_returns_all_shopping_factors(self):
        factors = (
            IndiaShoppingSourceAdapter
            .get_all_factors()
        )

        self.assertEqual(
            len(factors),
            2,
        )

        expected_factors = {
            "Clothing": Decimal("0.0411"),
            "Footwear": Decimal("0.0268"),
        }

        actual_factors = {
            factor.category_name: factor.factor
            for factor in factors
        }

        self.assertEqual(
            actual_factors,
            expected_factors,
        )

    def test_shopping_factors_use_rupee_unit(self):
        factors = (
            IndiaShoppingSourceAdapter
            .get_all_factors()
        )

        for factor in factors:
            self.assertEqual(
                factor.unit,
                "kgCO2e/₹",
            )

    def test_shopping_factors_have_correct_source_metadata(self):
        factors = (
            IndiaShoppingSourceAdapter
            .get_all_factors()
        )

        sources = {
            factor.category_name: factor.source
            for factor in factors
        }

        self.assertEqual(
            sources["Clothing"],
            (
                "India-specific household carbon footprint study - "
                "Readymade Garments"
            ),
        )

        self.assertEqual(
            sources["Footwear"],
            (
                "India-specific household carbon footprint study - "
                "Leather Footwear"
            ),
        )

        for factor in factors:
            self.assertEqual(
                factor.source_version,
                "Indian household expenditure study",
            )

    def test_returns_individual_shopping_factor(self):
        factor = (
            IndiaShoppingSourceAdapter
            .get_factor("Clothing")
        )

        self.assertEqual(
            factor.category_name,
            "Clothing",
        )

        self.assertEqual(
            factor.factor,
            Decimal("0.0411"),
        )

    def test_rejects_unsupported_shopping_category(self):
        with self.assertRaises(ValueError):
            IndiaShoppingSourceAdapter.get_factor(
                "Electronics"
            )

    def test_returns_all_factors_through_common_interface(self):
        factors = (
            IndiaShoppingSourceAdapter
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
                "Clothing",
                "Footwear",
            },
        )