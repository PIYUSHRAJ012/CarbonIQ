from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from recommendations.models import (
    OffsetProject,
    OffsetRecommendation,
)
from recommendations.services.offset_guidance.guidance import (
    INFORMATIONAL_GUIDANCE_MESSAGE,
    REDUCTION_FIRST_MESSAGE,
    build_offset_guidance,
    build_offset_guidance_collection,
)


class OffsetGuidanceCoordinatorTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="e9guidance@example.com",
            full_name="E9 Guidance User",
            password="test-password-123",
        )

    def make_project(
        self,
        *,
        name,
        project_id,
        country="India",
        project_type="Renewable Energy",
        sdg_impacts=None,
    ):
        return OffsetProject.objects.create(
            name=name,
            description="E9 guidance test project.",
            project_type=project_type,
            country=country,
            region="Karnataka",
            registry="Gold Standard",
            registry_project_id=project_id,
            registry_url=(
                f"https://example.com/{project_id}"
            ),
            status=OffsetProject.ProjectStatus.ACTIVE,
            sdg_impacts=(
                sdg_impacts
                if sdg_impacts is not None
                else [{"sdg": 13}]
            ),
            project_developer="Test Developer",
            certification_documents_url=(
                f"https://example.com/{project_id}/documents"
            ),
            source_last_verified_at=(
                timezone.now()
                - timedelta(days=5)
            ),
            is_active=True,
        )

    def make_recommendation(
        self,
        *,
        project,
        score="85.0000",
        indicative_tonnes="1.2500",
    ):
        return OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=project,
            score=Decimal(score),
            reason="E9 guidance test recommendation.",
            indicative_tonnes=Decimal(
                indicative_tonnes
            ),
            status=OffsetRecommendation.Status.ACTIVE,
        )

    def test_build_guidance_returns_unified_contract(self):
        project = self.make_project(
            name="Guidance Project",
            project_id="E9-GUIDANCE-001",
        )

        recommendation = self.make_recommendation(
            project=project,
            score="87.5000",
        )

        guidance = build_offset_guidance(
            recommendation
        )

        self.assertEqual(
            guidance.recommendation_id,
            recommendation.id,
        )

        self.assertEqual(
            guidance.project.project_name,
            project.name,
        )

        self.assertEqual(
            guidance.project.score,
            Decimal("87.5000"),
        )

        self.assertEqual(
            guidance.indicative_tonnes,
            Decimal("1.2500"),
        )

    def test_guidance_contains_verification(self):
        project = self.make_project(
            name="Verification Guidance",
            project_id="E9-GUIDANCE-002",
        )

        recommendation = self.make_recommendation(
            project=project,
        )

        guidance = build_offset_guidance(
            recommendation
        )

        self.assertEqual(
            guidance.verification.registry,
            "Gold Standard",
        )

        self.assertEqual(
            guidance.verification.registry_project_id,
            "E9-GUIDANCE-002",
        )

        self.assertEqual(
            guidance.verification.state,
            "FRESH",
        )

    def test_guidance_contains_suitability(self):
        project = self.make_project(
            name="Suitability Guidance",
            project_id="E9-GUIDANCE-003",
        )

        recommendation = self.make_recommendation(
            project=project,
        )

        guidance = build_offset_guidance(
            recommendation
        )

        self.assertGreaterEqual(
            guidance.suitability.matched_factor_count,
            1,
        )

        self.assertEqual(
            guidance.suitability.score,
            recommendation.score,
        )

    def test_reduction_first_guidance_is_present(self):
        project = self.make_project(
            name="Reduction First",
            project_id="E9-GUIDANCE-004",
        )

        recommendation = self.make_recommendation(
            project=project,
        )

        guidance = build_offset_guidance(
            recommendation
        )

        self.assertEqual(
            guidance.reduction_first_message,
            REDUCTION_FIRST_MESSAGE,
        )

    def test_informational_disclaimer_is_present(self):
        project = self.make_project(
            name="Informational Guidance",
            project_id="E9-GUIDANCE-005",
        )

        recommendation = self.make_recommendation(
            project=project,
        )

        guidance = build_offset_guidance(
            recommendation
        )

        self.assertEqual(
            guidance.informational_message,
            INFORMATIONAL_GUIDANCE_MESSAGE,
        )

    def test_stored_indicative_tonnes_are_not_recalculated(self):
        project = self.make_project(
            name="Snapshot Guidance",
            project_id="E9-GUIDANCE-006",
        )

        recommendation = self.make_recommendation(
            project=project,
            indicative_tonnes="9.8765",
        )

        guidance = build_offset_guidance(
            recommendation
        )

        self.assertEqual(
            guidance.indicative_tonnes,
            Decimal("9.8765"),
        )

    def test_collection_orders_by_existing_score(self):
        project_a = self.make_project(
            name="Collection A",
            project_id="E9-GUIDANCE-A",
        )

        project_b = self.make_project(
            name="Collection B",
            project_id="E9-GUIDANCE-B",
        )

        recommendation_a = self.make_recommendation(
            project=project_a,
            score="70.0000",
        )

        recommendation_b = self.make_recommendation(
            project=project_b,
            score="92.0000",
        )

        result = build_offset_guidance_collection(
            [
                recommendation_a,
                recommendation_b,
            ]
        )

        self.assertEqual(
            len(result),
            2,
        )

        self.assertEqual(
            result[0].project.project_name,
            "Collection B",
        )

        self.assertEqual(
            result[1].project.project_name,
            "Collection A",
        )

    def test_collection_preserves_each_recommendation_snapshot(self):
        project_a = self.make_project(
            name="Snapshot A",
            project_id="E9-SNAPSHOT-A",
        )

        project_b = self.make_project(
            name="Snapshot B",
            project_id="E9-SNAPSHOT-B",
        )

        recommendation_a = self.make_recommendation(
            project=project_a,
            score="80.0000",
            indicative_tonnes="2.5000",
        )

        recommendation_b = self.make_recommendation(
            project=project_b,
            score="85.0000",
            indicative_tonnes="3.7500",
        )

        result = build_offset_guidance_collection(
            [
                recommendation_a,
                recommendation_b,
            ]
        )

        by_name = {
            item.project.project_name: item
            for item in result
        }

        self.assertEqual(
            by_name["Snapshot A"].indicative_tonnes,
            Decimal("2.5000"),
        )

        self.assertEqual(
            by_name["Snapshot B"].indicative_tonnes,
            Decimal("3.7500"),
        )