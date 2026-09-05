from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from recommendations.models import OffsetProject
from recommendations.services.offset_importer import (
    OffsetImportError,
    OffsetProjectImportService,
)
from recommendations.services.offset_sources.base import (
    NormalizedOffsetProject,
)


class OffsetProjectImportServiceTests(TestCase):
    def setUp(self):
        self.verified_at = timezone.now()

        self.project = NormalizedOffsetProject(
            name="India Solar Project",
            registry="Gold Standard",
            registry_project_id="GS-IMPORT-001",
            registry_url=(
                "https://registry.goldstandard.org/projects/details/100"
            ),
            description="Solar energy project.",
            project_type="Renewable Energy",
            country="India",
            region="Karnataka",
            standard="Gold Standard",
            status="ACTIVE",
            project_scale="Large",
            annual_estimated_credits=Decimal("10000.00"),
            sdg_impacts=(
                {
                    "sdg": 7,
                    "name": "Affordable and Clean Energy",
                },
                {
                    "sdg": 13,
                    "name": "Climate Action",
                },
            ),
            project_developer="Example Energy Ltd.",
            certification_documents_url=(
                "https://example.com/documents"
            ),
            source_last_verified_at=self.verified_at,
        )

    def test_new_project_is_created(self):
        result = OffsetProjectImportService.import_projects(
            [self.project]
        )

        self.assertEqual(result.created, 1)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.unchanged, 0)

        self.assertEqual(
            OffsetProject.objects.count(),
            1,
        )

        project = OffsetProject.objects.get(
            registry="Gold Standard",
            registry_project_id="GS-IMPORT-001",
        )

        self.assertEqual(
            project.name,
            "India Solar Project",
        )

    def test_importing_same_project_is_idempotent(self):
        first_result = (
            OffsetProjectImportService.import_projects(
                [self.project]
            )
        )

        second_result = (
            OffsetProjectImportService.import_projects(
                [self.project]
            )
        )

        self.assertEqual(first_result.created, 1)

        self.assertEqual(
            second_result.created,
            0,
        )

        self.assertEqual(
            second_result.updated,
            0,
        )

        self.assertEqual(
            second_result.unchanged,
            1,
        )

        self.assertEqual(
            OffsetProject.objects.count(),
            1,
        )

    def test_changed_project_metadata_is_updated(self):
        OffsetProjectImportService.import_projects(
            [self.project]
        )

        changed_project = NormalizedOffsetProject(
            **{
                **self.project.__dict__,
                "description": "Updated project description.",
                "project_developer": "Updated Developer Ltd.",
            }
        )

        result = OffsetProjectImportService.import_projects(
            [changed_project]
        )

        self.assertEqual(
            result.created,
            0,
        )

        self.assertEqual(
            result.updated,
            1,
        )

        project = OffsetProject.objects.get(
            registry="Gold Standard",
            registry_project_id="GS-IMPORT-001",
        )

        self.assertEqual(
            project.description,
            "Updated project description.",
        )

        self.assertEqual(
            project.project_developer,
            "Updated Developer Ltd.",
        )

    def test_different_registry_can_use_same_project_id(self):
        second_project = NormalizedOffsetProject(
            name="Another Registry Project",
            registry="Another Registry",
            registry_project_id="GS-IMPORT-001",
            registry_url="https://example.com/project/2",
            source_last_verified_at=self.verified_at,
        )

        result = OffsetProjectImportService.import_projects(
            [
                self.project,
                second_project,
            ]
        )

        self.assertEqual(
            result.created,
            2,
        )

        self.assertEqual(
            OffsetProject.objects.count(),
            2,
        )

    def test_multiple_projects_return_correct_statistics(self):
        second_project = NormalizedOffsetProject(
            name="India Wind Project",
            registry="Gold Standard",
            registry_project_id="GS-IMPORT-002",
            registry_url=(
                "https://registry.goldstandard.org/projects/details/101"
            ),
            country="India",
            project_type="Renewable Energy",
            source_last_verified_at=self.verified_at,
        )

        third_project = NormalizedOffsetProject(
            name="India Forest Project",
            registry="Gold Standard",
            registry_project_id="GS-IMPORT-003",
            registry_url=(
                "https://registry.goldstandard.org/projects/details/102"
            ),
            country="India",
            project_type="Forest Restoration",
            source_last_verified_at=self.verified_at,
        )

        result = OffsetProjectImportService.import_projects(
            [
                self.project,
                second_project,
                third_project,
            ]
        )

        self.assertEqual(
            result.created,
            3,
        )

        self.assertEqual(
            result.updated,
            0,
        )

        self.assertEqual(
            result.unchanged,
            0,
        )

    def test_missing_required_name_is_rejected(self):
        invalid_project = NormalizedOffsetProject(
            name="",
            registry="Gold Standard",
            registry_project_id="GS-INVALID-001",
            registry_url="https://example.com/project",
        )

        with self.assertRaises(OffsetImportError):
            OffsetProjectImportService.import_projects(
                [invalid_project]
            )

        self.assertEqual(
            OffsetProject.objects.count(),
            0,
        )

    def test_missing_registry_id_is_rejected(self):
        invalid_project = NormalizedOffsetProject(
            name="Invalid Project",
            registry="Gold Standard",
            registry_project_id="",
            registry_url="https://example.com/project",
        )

        with self.assertRaises(OffsetImportError):
            OffsetProjectImportService.import_projects(
                [invalid_project]
            )

        self.assertEqual(
            OffsetProject.objects.count(),
            0,
        )

    def test_negative_credits_are_rejected(self):
        invalid_project = NormalizedOffsetProject(
            name="Invalid Credits Project",
            registry="Gold Standard",
            registry_project_id="GS-INVALID-002",
            registry_url="https://example.com/project",
            annual_estimated_credits=Decimal("-10"),
        )

        with self.assertRaises(OffsetImportError):
            OffsetProjectImportService.import_projects(
                [invalid_project]
            )

        self.assertEqual(
            OffsetProject.objects.count(),
            0,
        )

    def test_failed_import_rolls_back_previous_projects(self):
        valid_project = self.project

        invalid_project = NormalizedOffsetProject(
            name="",
            registry="Gold Standard",
            registry_project_id="GS-ROLLBACK-001",
            registry_url="https://example.com/project",
        )

        with self.assertRaises(OffsetImportError):
            OffsetProjectImportService.import_projects(
                [
                    valid_project,
                    invalid_project,
                ]
            )

        self.assertEqual(
            OffsetProject.objects.count(),
            0,
        )

    def test_source_verification_timestamp_is_persisted(self):
        OffsetProjectImportService.import_projects(
            [self.project]
        )

        project = OffsetProject.objects.get(
            registry_project_id="GS-IMPORT-001"
        )

        self.assertEqual(
            project.source_last_verified_at,
            self.verified_at,
        )

    def test_missing_verification_timestamp_is_generated(self):
        project = NormalizedOffsetProject(
            name="Timestamp Project",
            registry="Gold Standard",
            registry_project_id="GS-TIME-001",
            registry_url="https://example.com/project/time",
        )

        before = timezone.now()

        OffsetProjectImportService.import_projects(
            [project]
        )

        after = timezone.now()

        imported_project = OffsetProject.objects.get(
            registry_project_id="GS-TIME-001"
        )

        self.assertGreaterEqual(
            imported_project.source_last_verified_at,
            before,
        )

        self.assertLessEqual(
            imported_project.source_last_verified_at,
            after,
        )

    def test_reimporting_identical_project_is_counted_as_unchanged(
        self,
    ):
        OffsetProjectImportService.import_projects(
            [self.project]
        )

        result = OffsetProjectImportService.import_projects(
            [self.project]
        )

        self.assertEqual(
            result.created,
            0,
        )

        self.assertEqual(
            result.updated,
            0,
        )

        self.assertEqual(
            result.unchanged,
            1,
        )


    def test_verification_timestamp_is_refreshed_when_project_is_unchanged(
        self,
    ):
        OffsetProjectImportService.import_projects(
            [self.project]
        )

        project_before = OffsetProject.objects.get(
            registry_project_id="GS-IMPORT-001"
        )

        original_timestamp = (
            project_before.source_last_verified_at
        )

        result = OffsetProjectImportService.import_projects(
            [self.project]
        )

        project_after = OffsetProject.objects.get(
            registry_project_id="GS-IMPORT-001"
        )

        self.assertEqual(
            result.unchanged,
            1,
        )

        self.assertGreaterEqual(
            project_after.source_last_verified_at,
            original_timestamp,
        )