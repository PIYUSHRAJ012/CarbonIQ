from decimal import Decimal

from django.test import TestCase

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.emission_import.importer import (
    EmissionFactorImporter,
)
from carbon.services.emission_import.transport import (
    IndiaTransportSourceAdapter,
)


class IndiaTransportImportTests(TestCase):
    """
    Tests the end-to-end persistence of the India-specific
    transportation emission factor.
    """

    def setUp(self):
        self.category = ActivityCategory.objects.create(
            name="Transportation",
            description="Transportation activity",
            unit="km",
            display_order=2,
            is_active=True,
        )

    def test_imports_transport_factor(self):
        imported_factor = (
            IndiaTransportSourceAdapter
            .get_default_transport_factor()
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
            Decimal("0.1264"),
        )

        self.assertEqual(
            factor.source,
            (
                "Ministry of Environment, Forest and "
                "Climate Change (India) - Low Carbon Lifestyles"
            ),
        )

        self.assertEqual(
            factor.effective_from.year,
            2016,
        )

        self.assertTrue(
            factor.is_active
        )

    def test_reimport_is_idempotent(self):
        imported_factor = (
            IndiaTransportSourceAdapter
            .get_default_transport_factor()
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