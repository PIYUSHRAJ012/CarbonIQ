from datetime import timedelta
from decimal import Decimal

from django.test import TestCase
from django.urls import reverse
from django.utils import timezone

from accounts.models import CustomUser
from recommendations.models import (
    OffsetProject,
    OffsetRecommendation,
    Recommendation,
    UserRecommendation,
)


class RecommendationsViewE9Tests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="e9view@example.com",
            full_name="E9 View User",
            password="test-password-123",
        )

        self.client.login(
            email="e9view@example.com",
            password="test-password-123",
        )

    def make_offset_project(
        self,
        *,
        name,
        project_id,
    ):
        return OffsetProject.objects.create(
            name=name,
            description="E9 view test project.",
            project_type="Renewable Energy",
            country="India",
            region="Karnataka",
            registry="Gold Standard",
            registry_project_id=project_id,
            registry_url=(
                f"https://example.com/{project_id}"
            ),
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_developer="Test Developer",
            certification_documents_url=(
                f"https://example.com/{project_id}/documents"
            ),
            source_last_verified_at=(
                timezone.now()
                - timedelta(days=5)
            ),
            sdg_impacts=[
                {"sdg": 13},
            ],
            is_active=True,
        )

    def make_offset_recommendation(
        self,
        *,
        project,
        score,
    ):
        return OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=project,
            score=Decimal(score),
            reason="E9 view integration test.",
            indicative_tonnes=Decimal("1.2500"),
            status=OffsetRecommendation.Status.ACTIVE,
        )

    def test_page_loads_with_e9_guidance_context(self):
        project = self.make_offset_project(
            name="E9 View Project",
            project_id="E9-VIEW-001",
        )

        self.make_offset_recommendation(
            project=project,
            score="91.5000",
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertIn(
            "offset_guidance",
            response.context,
        )

        guidance = response.context["offset_guidance"]

        self.assertEqual(
            len(guidance),
            1,
        )

        self.assertEqual(
            guidance[0].project.project_name,
            "E9 View Project",
        )

        self.assertEqual(
            guidance[0].project.score,
            Decimal("91.5000"),
        )

    def test_only_authenticated_users_offset_guidance_is_loaded(self):
        other_user = CustomUser.objects.create_user(
            email="other-e9view@example.com",
            full_name="Other E9 User",
            password="test-password-123",
        )

        project = self.make_offset_project(
            name="Other User Project",
            project_id="E9-VIEW-002",
        )

        OffsetRecommendation.objects.create(
            user=other_user,
            offset_project=project,
            score=Decimal("99.0000"),
            reason="Other-user test.",
            indicative_tonnes=Decimal("2.0000"),
            status=OffsetRecommendation.Status.ACTIVE,
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        guidance = response.context["offset_guidance"]

        self.assertEqual(
            guidance,
            (),
        )

    def test_non_active_offset_recommendations_are_excluded(self):
        project = self.make_offset_project(
            name="Inactive Recommendation",
            project_id="E9-VIEW-003",
        )

        OffsetRecommendation.objects.create(
            user=self.user,
            offset_project=project,
            score=Decimal("95.0000"),
            reason="Inactive test.",
            indicative_tonnes=Decimal("2.0000"),
            status=OffsetRecommendation.Status.COMPLETED,
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertEqual(
            response.context["offset_guidance"],
            (),
        )

    def test_existing_user_recommendation_sections_remain_available(self):
        category = None

        sustainability = Recommendation.objects.create(
            title="Reduce electricity consumption",
            description="Test sustainability action.",
            category=category,
            action_type=Recommendation.ActionType.SUSTAINABILITY,
            priority=80,
            is_active=True,
        )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=sustainability,
            score=Decimal("88.0000"),
            reason="Test sustainability recommendation.",
            status=UserRecommendation.Status.ACTIVE,
        )

        offset = Recommendation.objects.create(
            title="Consider residual emission offsets",
            description="Test offset action.",
            category=category,
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
            is_active=True,
        )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=offset,
            score=Decimal("70.0000"),
            reason="Test offset action.",
            status=UserRecommendation.Status.ACTIVE,
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertEqual(
            response.context[
                "sustainability_recommendations"
            ].count(),
            1,
        )

        self.assertEqual(
            response.context[
                "offset_recommendations"
            ].count(),
            1,
        )

    def test_e9_guidance_details_are_rendered(self):
        project = self.make_offset_project(
            name="Rendered E9 Project",
            project_id="E9-RENDER-001",
        )

        self.make_offset_recommendation(
            project=project,
            score="94.5000",
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertContains(
            response,
            "Carbon Offset Guidance",
        )

        self.assertContains(
            response,
            "Rendered E9 Project",
        )

        self.assertContains(
            response,
            "Gold Standard",
        )

        self.assertContains(
            response,
            "E9-RENDER-001",
        )

        self.assertContains(
            response,
            "Recently verified",
        )

        self.assertContains(
            response,
            "Why this project may suit you",
        )

        self.assertContains(
            response,
            "Indicative offset equivalent",
        )

    def test_e9_source_links_are_rendered(self):
        project = self.make_offset_project(
            name="E9 Source Links",
            project_id="E9-LINKS-001",
        )

        self.make_offset_recommendation(
            project=project,
            score="89.0000",
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertContains(
            response,
            "https://example.com/E9-LINKS-001",
        )

        self.assertContains(
            response,
            "https://example.com/E9-LINKS-001/documents",
        )

        self.assertContains(
            response,
            "View Registry",
        )

        self.assertContains(
            response,
            "Certification / Documents",
        )

    def test_other_users_projects_are_not_rendered(self):
        other_user = CustomUser.objects.create_user(
            email="e9template-other@example.com",
            full_name="Other Template User",
            password="test-password-123",
        )

        project = self.make_offset_project(
            name="PRIVATE OTHER USER PROJECT",
            project_id="E9-PRIVATE-001",
        )

        OffsetRecommendation.objects.create(
            user=other_user,
            offset_project=project,
            score=Decimal("99.0000"),
            reason="Private recommendation.",
            indicative_tonnes=Decimal("5.0000"),
            status=OffsetRecommendation.Status.ACTIVE,
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertNotContains(
            response,
            "PRIVATE OTHER USER PROJECT",
        )

        self.assertNotContains(
            response,
            "E9-PRIVATE-001",
        )

    def test_project_name_is_html_escaped(self):
        project = self.make_offset_project(
            name="<script>alert('xss')</script>",
            project_id="E9-XSS-001",
        )

        self.make_offset_recommendation(
            project=project,
            score="91.0000",
        )

        response = self.client.get(
            reverse("recommendations:list")
        )

        self.assertEqual(
            response.status_code,
            200,
        )

        self.assertNotContains(
            response,
            "<script>alert('xss')</script>",
            html=False,
        )

        self.assertContains(
            response,
            "&lt;script&gt;",
            html=False,
        )

        self.assertContains(
            response,
            "&lt;/script&gt;",
            html=False,
        )