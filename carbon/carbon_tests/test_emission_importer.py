from datetime import date
from decimal import Decimal

from django.test import TestCase

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.emission_import.base import ImportedEmissionFactor
from carbon.services.emission_import.importer import (
    EmissionFactorImporter,
)


class EmissionFactorImporterTests(TestCase):
    """
    Tests for EmissionFactorImporter.
    """

    def setUp(self):
        self.category = ActivityCategory.objects.create(
            name="Test Electricity",
            description="Test electricity category",
            unit="kWh",
            display_order=999,
            is_active=True,
        )

        self.imported_factor = ImportedEmissionFactor(
            category_name="Test Electricity",
            factor=Decimal("0.711725483062134"),
            unit="kgCO2/kWh",
            source="Test Official Source",
            source_version="Version 1.0",
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )

    def test_creates_new_emission_factor(self):
        factor, created = (
            EmissionFactorImporter.import_factor(
                self.imported_factor
            )
        )

        self.assertTrue(created)

        self.assertEqual(
            factor.activity_category,
            self.category,
        )

        self.assertEqual(
            factor.factor,
            Decimal("0.7117"),
        )

        self.assertEqual(
            factor.source,
            "Test Official Source",
        )

        self.assertEqual(
            factor.effective_from,
            date(2026, 4, 1),
        )

        self.assertIsNone(
            factor.effective_to
        )

    def test_identical_import_is_idempotent(self):
        first, created_first = (
            EmissionFactorImporter.import_factor(
                self.imported_factor
            )
        )

        second, created_second = (
            EmissionFactorImporter.import_factor(
                self.imported_factor
            )
        )

        self.assertTrue(created_first)
        self.assertFalse(created_second)

        self.assertEqual(
            first.id,
            second.id,
        )

        self.assertEqual(
            EmissionFactor.objects.count(),
            1,
        )

    def test_new_version_closes_previous_factor(self):
        old_factor = EmissionFactor.objects.create(
            activity_category=self.category,
            factor=Decimal("0.7080"),
            source="Test Official Source",
            effective_from=date(2025, 4, 1),
            effective_to=None,
            is_active=True,
        )

        new_import = ImportedEmissionFactor(
            category_name="Test Electricity",
            factor=Decimal("0.711725483062134"),
            unit="kgCO2/kWh",
            source="Test Official Source",
            source_version="Version 2.0",
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )

        new_factor, created = (
            EmissionFactorImporter.import_factor(
                new_import
            )
        )

        self.assertTrue(created)

        old_factor.refresh_from_db()

        self.assertEqual(
            old_factor.effective_to,
            date(2026, 3, 31),
        )

        self.assertEqual(
            new_factor.effective_from,
            date(2026, 4, 1),
        )

        self.assertIsNone(
            new_factor.effective_to
        )

    def test_conflicting_same_date_factor_is_rejected(self):
        EmissionFactor.objects.create(
            activity_category=self.category,
            factor=Decimal("0.7080"),
            source="Test Official Source",
            effective_from=date(2026, 4, 1),
            effective_to=None,
            is_active=True,
        )

        conflicting_import = ImportedEmissionFactor(
            category_name="Test Electricity",
            factor=Decimal("0.6500"),
            unit="kgCO2/kWh",
            source="Test Official Source",
            source_version="Version 99.0",
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )

        with self.assertRaises(ValueError):
            EmissionFactorImporter.import_factor(
                conflicting_import
            )

    def test_inactive_category_is_rejected(self):
        self.category.is_active = False
        self.category.save()

        with self.assertRaises(ValueError):
            EmissionFactorImporter.import_factor(
                self.imported_factor
            )

    def test_invalid_factor_is_rejected(self):
        invalid_import = ImportedEmissionFactor(
            category_name="Test Electricity",
            factor=Decimal("0"),
            unit="kgCO2/kWh",
            source="Test Official Source",
            source_version="Version 1.0",
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )

        with self.assertRaises(ValueError):
            EmissionFactorImporter.import_factor(
                invalid_import
            )

    def test_new_version_is_idempotent(self):
        first_import = ImportedEmissionFactor(
            category_name="Test Electricity",
            factor=Decimal("0.7117"),
            unit="kgCO2/kWh",
            source="Test Official Source",
            source_version="Version 21.0",
            effective_from=date(2024, 4, 1),
            effective_to=None,
        )

        second_import = ImportedEmissionFactor(
            category_name="Test Electricity",
            factor=Decimal("0.7012"),
            unit="kgCO2/kWh",
            source="Test Official Source",
            source_version="Version 22.0",
            effective_from=date(2025, 4, 1),
            effective_to=None,
        )

        first_factor, first_created = (
            EmissionFactorImporter.import_factor(
                first_import
            )
        )

        second_factor, second_created = (
            EmissionFactorImporter.import_factor(
                second_import
            )
        )

        repeat_factor, repeat_created = (
            EmissionFactorImporter.import_factor(
                second_import
            )
        )

        self.assertTrue(first_created)
        self.assertTrue(second_created)
        self.assertFalse(repeat_created)

        self.assertEqual(
            second_factor.id,
            repeat_factor.id,
        )

        self.assertEqual(
            EmissionFactor.objects.count(),
            2,
        )

        first_factor.refresh_from_db()

        self.assertEqual(
            first_factor.effective_to,
            date(2025, 3, 31),
        )

        self.assertEqual(
            second_factor.effective_from,
            date(2025, 4, 1),
        )

        self.assertIsNone(
            second_factor.effective_to,
        )