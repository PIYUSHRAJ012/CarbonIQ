from datetime import date
from decimal import Decimal
from pathlib import Path

from django.test import TestCase

from carbon.models import ActivityCategory
from carbon.services.emission_import.base import ImportedEmissionFactor
from carbon.services.emission_import.coordinator import (
    EmissionFactorImportCoordinator,
)
from unittest.mock import Mock, patch


class EmissionFactorImportCoordinatorTests(TestCase):
    """
    Tests for the emission-factor import coordinator.
    """

    def setUp(self):
        self.category = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

    @patch(
        "carbon.services.emission_import.coordinator."
        "CEASourceRetriever.download_latest"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "CEASourceAdapter.parse_workbook"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "EmissionFactorImporter.import_factor"
    )
    def test_import_latest_cea_factor(
        self,
        mock_import_factor,
        mock_parse_workbook,
        mock_download_latest,
    ):
        workbook_path = Path("test-cea.xlsx")

        metadata = Mock(
            version="Version 21.0",
            source_url="https://example.com/cea.xlsx",
        )

        imported_factor = ImportedEmissionFactor(
            category_name="Electricity",
            factor=Decimal("0.711725483062134"),
            unit="kgCO2/kWh",
            source=(
                "Central Electricity Authority (India) - "
                "CO2 Baseline Database"
            ),
            source_version="Version 21.0",
            effective_from=date(2024, 4, 1),
            effective_to=None,
        )

        emission_factor = Mock(
            id=123,
        )

        mock_download_latest.return_value = (
            metadata,
            workbook_path,
        )

        mock_parse_workbook.return_value = (
            imported_factor
        )

        mock_import_factor.return_value = (
            emission_factor,
            True,
        )

        with patch.object(
            Path,
            "unlink",
        ) as mock_unlink:
            result = (
                EmissionFactorImportCoordinator
                .import_latest_cea_factor()
            )

        mock_download_latest.assert_called_once_with(
            destination_dir=None,
        )

        mock_parse_workbook.assert_called_once_with(
            workbook_path,
        )

        mock_import_factor.assert_called_once_with(
            imported_factor,
        )

        mock_unlink.assert_called_once_with(
            missing_ok=True,
        )

        self.assertEqual(
            result["source_version"],
            "Version 21.0",
        )

        self.assertEqual(
            result["category"],
            "Electricity",
        )

        self.assertEqual(
            result["factor"],
            Decimal("0.711725483062134"),
        )

        self.assertEqual(
            result["unit"],
            "kgCO2/kWh",
        )

        self.assertEqual(
            result["effective_from"],
            date(2024, 4, 1),
        )

        self.assertTrue(
            result["created"]
        )

        self.assertEqual(
            result["emission_factor_id"],
            123,
        )

    @patch(
        "carbon.services.emission_import.coordinator."
        "CEASourceRetriever.download_latest"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "CEASourceAdapter.parse_workbook"
    )
    def test_workbook_is_cleaned_up_when_parsing_fails(
        self,
        mock_parse_workbook,
        mock_download_latest,
    ):
        workbook_path = Path("test-cea.xlsx")

        metadata = Mock(
            version="Version 21.0",
            source_url="https://example.com/cea.xlsx",
        )

        mock_download_latest.return_value = (
            metadata,
            workbook_path,
        )

        mock_parse_workbook.side_effect = ValueError(
            "Invalid CEA workbook"
        )

        with patch.object(
            Path,
            "unlink",
        ) as mock_unlink:
            with self.assertRaises(ValueError):
                (
                    EmissionFactorImportCoordinator
                    .import_latest_cea_factor()
                )

        mock_unlink.assert_called_once_with(
            missing_ok=True,
        )

    @patch(
        "carbon.services.emission_import.coordinator."
        "EmissionFactorImporter.import_factor"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "IndiaWasteSourceAdapter.get_factors"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "IndiaShoppingSourceAdapter.get_factors"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "IndiaFoodSourceAdapter.get_factors"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "IndiaFuelSourceAdapter.get_factors"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "IndiaTransportSourceAdapter.get_factors"
    )
    @patch(
        "carbon.services.emission_import.coordinator."
        "EmissionFactorImportCoordinator.import_latest_cea_factor"
    )
    def test_import_all_factors(
        self,
        mock_cea_import,
        mock_transport_factors,
        mock_fuel_factors,
        mock_food_factors,
        mock_shopping_factors,
        mock_waste_factors,
        mock_import_factor,
    ):
        mock_cea_import.return_value = {
            "source": "CEA",
            "source_version": "Version 21.0",
            "category": "Electricity",
            "factor": Decimal("0.7117"),
            "unit": "kgCO2/kWh",
            "effective_from": date(2024, 4, 1),
            "effective_to": None,
            "created": False,
            "emission_factor_id": 1,
        }

        transport_factor = ImportedEmissionFactor(
            category_name="Transportation",
            factor=Decimal("0.12637"),
            unit="kgCO2/km",
            source="Transport Source",
            source_version="Version 1",
            effective_from=date(2016, 1, 1),
            effective_to=None,
        )

        petrol_factor = ImportedEmissionFactor(
            category_name="Petrol",
            factor=Decimal("2.37135"),
            unit="kgCO2/litre",
            source="Fuel Source",
            source_version="Version 1",
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )

        diesel_factor = ImportedEmissionFactor(
            category_name="Diesel",
            factor=Decimal("2.64831"),
            unit="kgCO2/litre",
            source="Fuel Source",
            source_version="Version 1",
            effective_from=date(2026, 4, 1),
            effective_to=None,
        )

        food_factor = ImportedEmissionFactor(
            category_name="Rice & Grain",
            factor=Decimal("3.6"),
            unit="kgCO2e/kg",
            source="Food Source",
            source_version="Version 1",
            effective_from=date(2025, 1, 1),
            effective_to=None,
        )

        shopping_factor = ImportedEmissionFactor(
            category_name="Clothing",
            factor=Decimal("0.0411"),
            unit="kgCO2e/₹",
            source="Shopping Source",
            source_version="Version 1",
            effective_from=date(2005, 1, 1),
            effective_to=None,
        )

        waste_factor = ImportedEmissionFactor(
            category_name="Waste",
            factor=Decimal("0.32"),
            unit="kgCO2e/kg",
            source="Waste Source",
            source_version="Version 1",
            effective_from=date(2016, 1, 1),
            effective_to=None,
        )

        mock_transport_factors.return_value = [
            transport_factor
        ]

        mock_fuel_factors.return_value = [
            petrol_factor,
            diesel_factor,
        ]

        mock_food_factors.return_value = [
            food_factor
        ]

        mock_shopping_factors.return_value = [
            shopping_factor
        ]

        mock_waste_factors.return_value = [
            waste_factor
        ]

        mock_import_factor.return_value = (
            Mock(id=99),
            True,
        )

        result = (
            EmissionFactorImportCoordinator
            .import_all_factors()
        )

        self.assertEqual(
            result["created"],
            6,
        )

        self.assertEqual(
            result["already_current"],
            1,
        )

        self.assertEqual(
            len(result["sources"]),
            6,
        )

        mock_cea_import.assert_called_once()

        mock_transport_factors.assert_called_once()
        mock_fuel_factors.assert_called_once()
        mock_food_factors.assert_called_once()
        mock_shopping_factors.assert_called_once()
        mock_waste_factors.assert_called_once()

        self.assertEqual(
            mock_import_factor.call_count,
            6,
        )