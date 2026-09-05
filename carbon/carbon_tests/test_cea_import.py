from decimal import Decimal
from pathlib import Path

from django.test import SimpleTestCase

from carbon.services.emission_import.cea import CEASourceAdapter


class CEASourceAdapterTests(SimpleTestCase):
    """
    Tests for the CEA Version 21.0 source adapter.
    """

    @classmethod
    def setUpClass(cls):
        super().setUpClass()

        cls.workbook_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "CO2_Database_V_21.0.xlsx"
        )

    def test_parses_cea_version_and_latest_factor(self):
        imported_factor = CEASourceAdapter.parse_workbook(
            self.workbook_path
        )

        self.assertEqual(
            imported_factor.category_name,
            "Electricity",
        )

        self.assertEqual(
            imported_factor.factor,
            Decimal("0.711725483062134"),
        )

        self.assertEqual(
            imported_factor.unit,
            "kgCO2/kWh",
        )

        self.assertEqual(
            imported_factor.source_version,
            "Version 21.0",
        )

        self.assertEqual(
            imported_factor.effective_from.year,
            2024,
        )

        self.assertEqual(
            imported_factor.effective_from.month,
            4,
        )

        self.assertEqual(
            imported_factor.effective_from.day,
            1,
        )

    def test_rejects_missing_workbook(self):
        missing_path = (
            Path(__file__).resolve().parent
            / "fixtures"
            / "does_not_exist.xlsx"
        )

        with self.assertRaises(ValueError):
            CEASourceAdapter.parse_workbook(missing_path)

    def test_returns_factors_through_common_interface(self):
        factors = (
            CEASourceAdapter
            .get_factors_from_workbook(
                self.workbook_path
            )
        )

        self.assertEqual(
            len(factors),
            1,
        )

        self.assertEqual(
            factors[0].category_name,
            "Electricity",
        )

        self.assertEqual(
            factors[0].factor,
            Decimal("0.711725483062134"),
        )