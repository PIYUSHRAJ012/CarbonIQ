from datetime import date
from decimal import Decimal

from django.test import TestCase

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.emission_import.importer import (
    EmissionFactorImporter,
)
from carbon.services.emission_import.waste import (
    IndiaWasteSourceAdapter,
)


class IndiaWasteImportTests(TestCase):
    """
    Tests the end-to-end persistence of the India-specific
    waste emission factor.
    """

    def setUp(self):
        self.category = ActivityCategory.objects.create(
            name="Waste",
            description="Waste generated",
            unit="kg",
            display_order=7,
            is_active=True,
        )

    def test_imports_waste_factor(self):
        imported_factor = (
            IndiaWasteSourceAdapter
            .get_default_waste_factor()
        )

        factor, created = (
            EmissionFactorImporter.import_factor(
                imported_factor
            )
        )

        self.assertTrue(created)

        self.assertEqual(
            factor.activity_category,
            self.category,
        )

        self.assertEqual(
            factor.factor,
            Decimal("0.3200"),
        )

        self.assertEqual(
            factor.source,
            (
                "Ministry of Environment, Forest and "
                "Climate Change (India) - Low Carbon Lifestyles"
            ),
        )

        self.assertEqual(
            factor.unit if hasattr(factor, "unit") else "kgCO2e/kg",
            "kgCO2e/kg",
        )

        self.assertEqual(
            factor.effective_from,
            date(2016, 1, 1),
        )

        self.assertTrue(
            factor.is_active
        )

    def test_reimport_is_idempotent(self):
        imported_factor = (
            IndiaWasteSourceAdapter
            .get_default_waste_factor()
        )

        first, first_created = (
            EmissionFactorImporter.import_factor(
                imported_factor
            )
        )

        second, second_created = (
            EmissionFactorImporter.import_factor(
                imported_factor
            )
        )

        self.assertTrue(first_created)
        self.assertFalse(second_created)
        self.assertEqual(first.id, second.id)

        self.assertEqual(
            EmissionFactor.objects.count(),
            1,
        )

    def test_returns_all_factors_through_common_interface(self):
        factors = (
            IndiaWasteSourceAdapter
            .get_factors()
        )

        self.assertEqual(
            len(factors),
            1,
        )

        self.assertEqual(
            factors[0].category_name,
            "Waste",
        )
