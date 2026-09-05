from unittest.mock import patch

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase


class ImportEmissionFactorsCommandTests(TestCase):
    """
    Tests for the unified import_emission_factors management command.
    """

    @patch(
        "carbon.management.commands.import_emission_factors."
        "EmissionFactorImportCoordinator.import_all_factors"
    )
    def test_command_reports_success(
        self,
        mock_import,
    ):
        mock_import.return_value = {
            "created": 0,
            "already_current": 15,
            "sources": [
                {
                    "source": "CEA",
                    "source_version": "Version 21.0",
                    "category": "Electricity",
                    "factor": "0.7117",
                    "unit": "kgCO2/kWh",
                    "effective_from": "2024-04-01",
                    "effective_to": None,
                    "created": False,
                    "emission_factor_id": 6,
                },
                {
                    "source": "IndiaFuelSourceAdapter",
                    "created": 0,
                    "already_current": 2,
                    "factors": [
                        {
                            "category": "Petrol",
                            "factor": "2.37135",
                            "unit": "kgCO2/litre",
                            "source_version": "CAFE 2027",
                        },
                        {
                            "category": "Diesel",
                            "factor": "2.64831",
                            "unit": "kgCO2/litre",
                            "source_version": "CAFE 2027",
                        },
                    ],
                },
            ],
        }

        call_command("import_emission_factors")

        mock_import.assert_called_once_with()

    @patch(
        "carbon.management.commands.import_emission_factors."
        "EmissionFactorImportCoordinator.import_all_factors"
    )
    def test_command_reports_failure(
        self,
        mock_import,
    ):
        mock_import.side_effect = RuntimeError(
            "Source unavailable"
        )

        with self.assertRaises(CommandError):
            call_command("import_emission_factors")

        mock_import.assert_called_once_with()