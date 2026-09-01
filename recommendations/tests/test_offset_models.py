from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import IntegrityError
from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from recommendations.models import (
    OffsetProject,
    OffsetRecommendation,
)


class OffsetProjectModelTests(TestCase):
    def setUp(self):
        self.verified_at = timezone.now()

        self.project = OffsetProject.objects.create(
            name="Solar Energy Project",
            description=(
                "A renewable energy project generating clean electricity."
            ),
            project_type="Renewable Energy",
            country="India",
            region="Karnataka",
            registry="Gold Standard",
            registry_project_id="GS-TEST-001",
            registry_url=(
                "https://registry.goldstandard.org/projects/details/1"
            ),
            standard="Gold Standard",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Large",
            annual_estimated_credits=Decimal("12500.00"),
            sdg_impacts=[
                {"sdg": 7, "name": "Affordable and Clean Energy"},
                {"sdg": 13, "name": "Climate Action"},
            ],
            project_developer="Test Renewable Energy Ltd.",
            certification_documents_url=(
                "https://example.com/certification.pdf"
            ),
            source_last_verified_at=self.verified_at,
            is_active=True,
        )

    def test_offset_project_is_created(self):
        self.assertEqual(
            OffsetProject.objects.count(),
            1,
        )

        project = OffsetProject.objects.get(
            registry_project_id="GS-TEST-001"
        )

        self.assertEqual(
            project.name,
            "Solar Energy Project",
        )

        self.assertEqual(
            project.registry,
            "Gold Standard",
        )

    def test_string_representation(self):
        self.assertEqual(
            str(self.project),
            "Solar Energy Project (GS-TEST-001)",
        )

    def test_registry_project_identity_must_be_unique(self):
        with self.assertRaises(IntegrityError):
            OffsetProject.objects.create(
                name="Another Project",
                registry="Gold Standard",
                registry_project_id="GS-TEST-001",
                registry_url=(
                    "https://registry.goldstandard.org/projects/details/2"
                ),
                source_last_verified_at=timezone.now(),
            )

    def test_same_project_id_can_exist_in_different_registries(self):
        project = OffsetProject.objects.create(
            name="Another Registry Project",
            registry="Another Registry",
            registry_project_id="GS-TEST-001",
            registry_url="https://example.com/project/2",
            source_last_verified_at=timezone.now(),
        )

        self.assertEqual(
            project.registry_project_id,
            "GS-TEST-001",
        )

        self.assertEqual(
            OffsetProject.objects.filter(
                registry_project_id="GS-TEST-001"
            ).count(),
            2,
        )

    def test_annual_estimated_credits_cannot_be_negative(self):
        project = OffsetProject(
            name="Invalid Project",
            registry="Gold Standard",
            registry_project_id="GS-NEGATIVE-001",
            registry_url="https://example.com/project/negative",
            annual_estimated_credits=Decimal("-1.00"),
            source_last_verified_at=timezone.now(),
        )

        with self.assertRaises(ValidationError):
            project.full_clean()

    def test_offset_project_defaults_to_unknown_status(self):
        project = OffsetProject.objects.create(
            name="Unknown Status Project",
            registry="Gold Standard",
            registry_project_id="GS-UNKNOWN-001",
            registry_url="https://example.com/project/unknown",
            source_last_verified_at=timezone.now(),
        )

        self.assertEqual(
            project.status,
            OffsetProject.ProjectStatus.UNKNOWN,
        )

    def test_offset_project_can_store_structured_sdg_impacts(self):
        self.assertEqual(
            self.project.sdg_impacts[0]["sdg"],
            7,
        )

        self.assertEqual(
            self.project.sdg_impacts[1]["sdg"],
            13,
        )

    def test_project_can_be_deactivated_without_deletion(self):
        self.project.is_active = False
        self.project.save(
            update_fields=["is_active"]
        )

        self.project.refresh_from_db()

        self.assertFalse(
            self.project.is_active
        )

        self.assertTrue(
            OffsetProject.objects.filter(
                pk=self.project.pk
            ).exists()
        )

    def test_source_verification_timestamp_is_stored(self):
        self.assertEqual(
            self.project.source_last_verified_at,
            self.verified_at,
        )


class OffsetRecommendationModelTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="user@example.com",
            full_name="Test User",
            password="test-password-123",
        )

        self.project = OffsetProject.objects.create(
            name="Wind Energy Project",
            description="Clean wind-energy project.",
            project_type="Renewable Energy",
            country="India",
            region="Tamil Nadu",
            registry="Gold Standard",
            registry_project_id="GS-TEST-002",
            registry_url=(
                "https://registry.goldstandard.org/projects/details/2"
            ),
            standard="Gold Standard",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Medium",
            annual_estimated_credits=Decimal("8500.00"),
            sdg_impacts=[
                {"sdg": 7, "name": "Affordable and Clean Energy"},
                {"sdg": 13, "name": "Climate Action"},
            ],
            project_developer="Test Wind Energy Ltd.",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        self.recommendation = OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=self.project,
            score=Decimal("87.5000"),
            reason=(
                "This renewable-energy project is relevant to "
                "your footprint profile."
            ),
            indicative_tonnes=Decimal("1.2500"),
            status=OffsetRecommendation.Status.ACTIVE,
        )

    def test_offset_recommendation_is_created(self):
        self.assertEqual(
            OffsetRecommendation.objects.count(),
            1,
        )

    def test_relationships_are_correct(self):
        self.assertEqual(
            self.recommendation.user,
            self.user,
        )

        self.assertEqual(
            self.recommendation.offset_project,
            self.project,
        )

    def test_string_representation(self):
        self.assertEqual(
            str(self.recommendation),
            "user@example.com - Wind Energy Project (87.5000)",
        )

    def test_default_status_is_active(self):
        recommendation = OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=self.project,
            score=Decimal("50.0000"),
            reason="Test recommendation.",
            indicative_tonnes=Decimal("0.5000"),
        )

        self.assertEqual(
            recommendation.status,
            OffsetRecommendation.Status.ACTIVE,
        )

    def test_indicative_tonnes_cannot_be_negative(self):
        recommendation = OffsetRecommendation(
            user=self.user,
            offset_project=self.project,
            score=Decimal("50.0000"),
            reason="Invalid recommendation.",
            indicative_tonnes=Decimal("-0.5000"),
        )

        with self.assertRaises(ValidationError):
            recommendation.full_clean()

    def test_zero_indicative_tonnes_is_valid_at_model_level(self):
        recommendation = OffsetRecommendation(
            user=self.user,
            offset_project=self.project,
            score=Decimal("50.0000"),
            reason="Zero-offset test.",
            indicative_tonnes=Decimal("0.0000"),
        )

        recommendation.full_clean()

    def test_generated_at_is_populated(self):
        self.assertIsNotNone(
            self.recommendation.generated_at
        )

    def test_lifecycle_status_can_change(self):
        self.recommendation.status = (
            OffsetRecommendation.Status.DISMISSED
        )

        self.recommendation.save(
            update_fields=["status"]
        )

        self.recommendation.refresh_from_db()

        self.assertEqual(
            self.recommendation.status,
            OffsetRecommendation.Status.DISMISSED,
        )

    def test_recommendation_is_owned_by_its_user(self):
        self.assertEqual(
            self.recommendation.user_id,
            self.user.id,
        )

    def test_multiple_projects_can_be_recommended_to_same_user(self):
        second_project = OffsetProject.objects.create(
            name="Forest Restoration Project",
            project_type="Forest Restoration",
            country="India",
            registry="Gold Standard",
            registry_project_id="GS-TEST-003",
            registry_url=(
                "https://registry.goldstandard.org/projects/details/3"
            ),
            standard="Gold Standard",
            source_last_verified_at=timezone.now(),
        )

        second_recommendation = OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=second_project,
            score=Decimal("75.0000"),
            reason="Alternative project.",
            indicative_tonnes=Decimal("1.2500"),
        )

        self.assertEqual(
            OffsetRecommendation.objects.filter(
                user=self.user
            ).count(),
            2,
        )

        self.assertEqual(
            second_recommendation.offset_project,
            second_project,
        )

    def test_old_recommendation_keeps_its_offset_snapshot(self):
        original_value = self.recommendation.indicative_tonnes

        self.recommendation.indicative_tonnes = Decimal("2.5000")

        # The test verifies that the persisted recommendation has
        # an explicitly stored snapshot value rather than deriving
        # it dynamically from the user's latest footprint.
        self.recommendation.save(
            update_fields=["indicative_tonnes"]
        )

        self.recommendation.refresh_from_db()

        self.assertNotEqual(
            self.recommendation.indicative_tonnes,
            original_value,
        )

        self.assertEqual(
            self.recommendation.indicative_tonnes,
            Decimal("2.5000"),
        )