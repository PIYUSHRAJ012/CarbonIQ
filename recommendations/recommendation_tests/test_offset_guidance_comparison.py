from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from recommendations.models import OffsetProject, OffsetRecommendation
from recommendations.services.offset_guidance.comparison import (
    build_project_comparison,
)


class OffsetGuidanceComparisonTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="e9comparison@example.com",
            full_name="E9 Comparison User",
            password="test-password-123",
        )

    def make_project(
        self,
        *,
        name,
        project_id,
        project_type="Renewable Energy",
        country="India",
        region="Karnataka",
        sdg_impacts=None,
        verified_days_ago=5,
    ):
        return OffsetProject.objects.create(
            name=name,
            description="E9 comparison test project.",
            project_type=project_type,
            country=country,
            region=region,
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
                - timedelta(days=verified_days_ago)
            ),
            is_active=True,
        )

    def make_recommendation(
        self,
        *,
        project,
        score,
    ):
        return OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=project,
            score=Decimal(score),
            reason="E9 comparison test recommendation.",
            indicative_tonnes=Decimal("0.5000"),
            status=OffsetRecommendation.Status.ACTIVE,
        )

    def test_higher_persisted_score_ranks_first(self):
        project_a = self.make_project(
            name="Project A",
            project_id="E9-COMP-A",
        )

        project_b = self.make_project(
            name="Project B",
            project_id="E9-COMP-B",
        )

        recommendation_a = self.make_recommendation(
            project=project_a,
            score="82.5000",
        )

        recommendation_b = self.make_recommendation(
            project=project_b,
            score="91.2500",
        )

        result = build_project_comparison(
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
            result[0].project_name,
            "Project B",
        )

        self.assertEqual(
            result[0].rank,
            1,
        )

        self.assertEqual(
            result[1].rank,
            2,
        )

    def test_scores_are_preserved_without_recalculation(self):
        project = self.make_project(
            name="Score Preservation",
            project_id="E9-SCORE-001",
        )

        recommendation = self.make_recommendation(
            project=project,
            score="73.1250",
        )

        result = build_project_comparison(
            [recommendation]
        )

        self.assertEqual(
            result[0].score,
            Decimal("73.1250"),
        )

    def test_registry_information_is_exposed(self):
        project = self.make_project(
            name="Registry Project",
            project_id="E9-REGISTRY-001",
        )

        recommendation = self.make_recommendation(
            project=project,
            score="80.0000",
        )

        result = build_project_comparison(
            [recommendation]
        )

        comparison = result[0]

        self.assertEqual(
            comparison.registry,
            "Gold Standard",
        )

        self.assertEqual(
            comparison.registry_project_id,
            "E9-REGISTRY-001",
        )

        self.assertEqual(
            comparison.registry_url,
            "https://example.com/E9-REGISTRY-001",
        )

    def test_project_metadata_is_exposed(self):
        project = self.make_project(
            name="Metadata Project",
            project_id="E9-METADATA-001",
            project_type="Renewable Energy",
            country="India",
            region="Karnataka",
        )

        recommendation = self.make_recommendation(
            project=project,
            score="85.0000",
        )

        comparison = build_project_comparison(
            [recommendation]
        )[0]

        self.assertEqual(
            comparison.project_type,
            "Renewable Energy",
        )

        self.assertEqual(
            comparison.country,
            "India",
        )

        self.assertEqual(
            comparison.region,
            "Karnataka",
        )

    def test_sdg_13_alignment_uses_explicit_metadata(self):
        project = self.make_project(
            name="Climate Project",
            project_id="E9-SDG-001",
            sdg_impacts=[
                {"sdg": 7},
                {"sdg": 13},
            ],
        )

        recommendation = self.make_recommendation(
            project=project,
            score="88.0000",
        )

        comparison = build_project_comparison(
            [recommendation]
        )[0]

        self.assertTrue(
            comparison.sdg_13_aligned
        )

    def test_sdg_13_is_false_when_not_explicitly_present(self):
        project = self.make_project(
            name="Non SDG13 Project",
            project_id="E9-SDG-002",
            sdg_impacts=[
                {"sdg": 7},
                {"sdg": 12},
            ],
        )

        recommendation = self.make_recommendation(
            project=project,
            score="78.0000",
        )

        comparison = build_project_comparison(
            [recommendation]
        )[0]

        self.assertFalse(
            comparison.sdg_13_aligned
        )

    def test_verification_information_is_exposed(self):
        project = self.make_project(
            name="Verified Project",
            project_id="E9-VERIFY-001",
            verified_days_ago=10,
        )

        recommendation = self.make_recommendation(
            project=project,
            score="90.0000",
        )

        comparison = build_project_comparison(
            [recommendation]
        )[0]

        self.assertEqual(
            comparison.verification_state,
            "FRESH",
        )

        self.assertEqual(
            comparison.days_since_verification,
            10,
        )

    def test_status_information_is_exposed(self):
        project = self.make_project(
            name="Status Project",
            project_id="E9-STATUS-001",
        )

        recommendation = self.make_recommendation(
            project=project,
            score="81.0000",
        )

        comparison = build_project_comparison(
            [recommendation]
        )[0]

        self.assertEqual(
            comparison.project_status,
            OffsetProject.ProjectStatus.ACTIVE,
        )

        self.assertEqual(
            comparison.project_status_label,
            "Active",
        )

    def test_suitability_count_is_exposed(self):
        project = self.make_project(
            name="Suitable Project",
            project_id="E9-SUIT-001",
            country="India",
            sdg_impacts=[
                {"sdg": 13},
            ],
        )

        recommendation = self.make_recommendation(
            project=project,
            score="86.0000",
        )

        comparison = build_project_comparison(
            [recommendation]
        )[0]

        self.assertGreaterEqual(
            comparison.suitability_match_count,
            1,
        )

    def test_empty_input_returns_empty_tuple(self):
        result = build_project_comparison([])

        self.assertEqual(
            result,
            (),
        )