from decimal import Decimal

from django.test import SimpleTestCase,TestCase

from carbon.services.emission_import.food import (
    IndiaFoodSourceAdapter,
)

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.emission_import.importer import (
    EmissionFactorImporter,
)

class IndiaFoodSourceAdapterTests(SimpleTestCase):
    """
    Tests for the India-relevant food emission-factor adapter.
    """

    def test_returns_all_food_factors(self):
        factors = (
            IndiaFoodSourceAdapter
            .get_all_factors()
        )

        self.assertEqual(
            len(factors),
            6,
        )

        expected_factors = {
            "Rice & Grain": Decimal("3.6"),
            "Legumes": Decimal("2.0"),
            "Milk": Decimal("3.2"),
            "Tofu": Decimal("3.2"),
            "Fruit": Decimal("0.9"),
            "Vegetables": Decimal("0.7"),
        }

        actual_factors = {
            factor.category_name: factor.factor
            for factor in factors
        }

        self.assertEqual(
            actual_factors,
            expected_factors,
        )

    def test_food_factors_use_kg_unit(self):
        factors = (
            IndiaFoodSourceAdapter
            .get_all_factors()
        )

        for factor in factors:
            self.assertEqual(
                factor.unit,
                "kgCO2e/kg",
            )

    def test_food_factors_have_source_metadata(self):
        factors = (
            IndiaFoodSourceAdapter
            .get_all_factors()
        )

        for factor in factors:
            self.assertEqual(
                factor.source_version,
                "NABARD Working Paper 2025-1",
            )

    def test_returns_individual_food_factor(self):
        factor = (
            IndiaFoodSourceAdapter
            .get_factor("Rice & Grain")
        )

        self.assertEqual(
            factor.category_name,
            "Rice & Grain",
        )

        self.assertEqual(
            factor.factor,
            Decimal("3.6"),
        )

    def test_rejects_unsupported_food_category(self):
        with self.assertRaises(ValueError):
            IndiaFoodSourceAdapter.get_factor(
                "Chicken"
            )

class IndiaFoodImportTests(TestCase):
    """
    Tests persistence of all India-relevant food emission factors.
    """

    def setUp(self):
        self.category_names = [
            "Rice & Grain",
            "Legumes",
            "Milk",
            "Tofu",
            "Fruit",
            "Vegetables",
        ]

        for index, name in enumerate(
            self.category_names,
            start=5,
        ):
            ActivityCategory.objects.create(
                name=name,
                description=f"{name} consumption",
                unit="kg",
                display_order=index,
                is_active=True,
            )

    def test_imports_all_food_factors(self):
        imported_factors = (
            IndiaFoodSourceAdapter.get_all_factors()
        )

        self.assertEqual(
            len(imported_factors),
            6,
        )

        for imported_factor in imported_factors:
            factor, created = (
                EmissionFactorImporter.import_factor(
                    imported_factor
                )
            )

            self.assertTrue(created)

            self.assertEqual(
                factor.activity_category.name,
                imported_factor.category_name,
            )

            self.assertEqual(
                factor.factor,
                imported_factor.factor,
            )

            self.assertEqual(
                factor.is_active,
                True,
            )

    def test_reimport_is_idempotent(self):
        imported_factors = (
            IndiaFoodSourceAdapter.get_all_factors()
        )

        for imported_factor in imported_factors:
            EmissionFactorImporter.import_factor(
                imported_factor
            )

        for imported_factor in imported_factors:
            _, created = (
                EmissionFactorImporter.import_factor(
                    imported_factor
                )
            )

            self.assertFalse(created)

        self.assertEqual(
            EmissionFactor.objects.count(),
            6,
        )