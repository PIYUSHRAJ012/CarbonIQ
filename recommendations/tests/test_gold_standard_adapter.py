from decimal import Decimal

from django.test import TestCase

from recommendations.services.offset_sources.base import (
    OffsetSourceError,
)
from recommendations.services.offset_sources.gold_standard import (
    GoldStandardAdapter,
)


class GoldStandardAdapterTests(TestCase):

    def setUp(self):
        self.adapter = GoldStandardAdapter()

        self.raw_project = {
            "GSID": "23755",
            "Project Name": (
                "Low Carbon Rice Cultivation in "
                "Mandi Bahauddin Punjab Pakistan"
            ),
            "Project Developer Name": "NetZeroAg Ltd",
            "Status": "Gold Standard Certified Project",
            "Sustainable Development Goals": (
                "5,1,4,13,12,3,2,6,8"
            ),
            "Project Type": "Other",
            "Country": "Pakistan",
            "Description": (
                "Low-carbon rice cultivation project."
            ),
            "Estimated Annual Credits": "51473",
            "Methodology": "",
            "Size": "Small Scale",
            "Programme of Activities": "VPA",
            "POA GSID": "23693",
        }

    def test_real_export_fields_are_normalized(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.registry,
            "Gold Standard",
        )

        self.assertEqual(
            project.registry_project_id,
            "GS23755",
        )

        self.assertEqual(
            project.name,
            "Low Carbon Rice Cultivation in "
            "Mandi Bahauddin Punjab Pakistan",
        )

        self.assertEqual(
            project.country,
            "Pakistan",
        )

        self.assertEqual(
            project.project_type,
            "Other",
        )

    def test_annual_credits_are_converted_to_decimal(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.annual_estimated_credits,
            Decimal("51473"),
        )

    def test_size_is_mapped_to_project_scale(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.project_scale,
            "Small Scale",
        )

    def test_developer_is_mapped(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.project_developer,
            "NetZeroAg Ltd",
        )

    def test_sdg_numbers_are_parsed(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.sdg_impacts,
            (
                {"sdg": 5},
                {"sdg": 1},
                {"sdg": 4},
                {"sdg": 13},
                {"sdg": 12},
                {"sdg": 3},
                {"sdg": 2},
                {"sdg": 6},
                {"sdg": 8},
            ),
        )

    def test_certified_project_is_active(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.status,
            "ACTIVE",
        )

    def test_listed_project_is_active(self):
        raw_project = {
            **self.raw_project,
            "Status": "Listed",
        }

        project = self.adapter.normalize_project(
            raw_project
        )

        self.assertEqual(
            project.status,
            "ACTIVE",
        )

    def test_certified_design_is_active(self):
        raw_project = {
            **self.raw_project,
            "Status": (
                "Gold Standard Certified Design"
            ),
        }

        project = self.adapter.normalize_project(
            raw_project
        )

        self.assertEqual(
            project.status,
            "ACTIVE",
        )

    def test_unknown_status_becomes_unknown(self):
        raw_project = {
            **self.raw_project,
            "Status": "Future Registry Status",
        }

        project = self.adapter.normalize_project(
            raw_project
        )

        self.assertEqual(
            project.status,
            "UNKNOWN",
        )

    def test_missing_gsid_is_rejected(self):
        raw_project = {
            **self.raw_project,
            "GSID": "",
        }

        with self.assertRaises(OffsetSourceError):
            self.adapter.normalize_project(
                raw_project
            )

    def test_missing_project_name_is_rejected(self):
        raw_project = {
            **self.raw_project,
            "Project Name": "",
        }

        with self.assertRaises(OffsetSourceError):
            self.adapter.normalize_project(
                raw_project
            )

    def test_missing_country_is_rejected(self):
        raw_project = {
            **self.raw_project,
            "Country": "",
        }

        with self.assertRaises(OffsetSourceError):
            self.adapter.normalize_project(
                raw_project
            )

    def test_current_export_schema_is_accepted(self):
        columns = list(
            self.adapter.REQUIRED_EXPORT_COLUMNS
        )

        self.adapter.validate_export_columns(
            columns
        )

    def test_missing_export_column_is_rejected(self):
        columns = list(
            self.adapter.REQUIRED_EXPORT_COLUMNS
        )

        columns.remove(
            "Estimated Annual Credits"
        )

        with self.assertRaises(
            OffsetSourceError
        ):
            self.adapter.validate_export_columns(
                columns
            )

    def test_registry_url_is_generated_from_gsid(self):
        project = self.adapter.normalize_project(
            self.raw_project
        )

        self.assertEqual(
            project.registry_url,
            "https://registry.goldstandard.org/"
            "projects/details/23755",
        )