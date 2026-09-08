from decimal import Decimal

from django.test import TestCase

from recommendations.models import OffsetProject
from recommendations.services.offset_guidance.suitability import (
    build_offset_suitability,
)

from django.utils import timezone

class OffsetGuidanceSuitabilityTests(TestCase):

    def make_project(
        self,
        *,
        country="India",
        project_type="Renewable Energy",
        sdg_impacts=None,
    ):
        return OffsetProject.objects.create(
            name="E9 Suitability Test Project",
            description="Test project.",
            project_type=project_type,
            country=country,
            registry="Gold Standard",
            registry_project_id="GS-SUITABILITY-001",
            registry_url=(
                "https://example.com/gs-suitability-001"
            ),
            status=OffsetProject.ProjectStatus.ACTIVE,
            sdg_impacts=(
                sdg_impacts
                if sdg_impacts is not None
                else [{"sdg": 13}]
            ),
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

    def test_india_project_matches_geographic_alignment(self):
        project = self.make_project()

        suitability = build_offset_suitability(
            project,
            score=Decimal("82.50"),
        )

        factor = next(
            factor
            for factor in suitability.factors
            if factor.key == "country_match"
        )

        self.assertTrue(factor.matched)

    def test_non_india_project_does_not_match_india_alignment(self):
        project = self.make_project(
            country="Nepal"
        )

        suitability = build_offset_suitability(
            project
        )

        factor = next(
            factor
            for factor in suitability.factors
            if factor.key == "country_match"
        )

        self.assertFalse(factor.matched)

    def test_sdg_13_match_uses_explicit_project_metadata(self):
        project = self.make_project(
            sdg_impacts=[
                {"sdg": 7},
                {"sdg": 13},
            ]
        )

        suitability = build_offset_suitability(
            project
        )

        factor = next(
            factor
            for factor in suitability.factors
            if factor.key == "sdg_13"
        )

        self.assertTrue(factor.matched)

    def test_missing_sdg_13_is_not_inferred(self):
        project = self.make_project(
            sdg_impacts=[
                {"sdg": 7},
            ]
        )

        suitability = build_offset_suitability(
            project
        )

        factor = next(
            factor
            for factor in suitability.factors
            if factor.key == "sdg_13"
        )

        self.assertFalse(factor.matched)

    def test_project_type_availability_is_reported(self):
        project = self.make_project(
            project_type="Renewable Energy"
        )

        suitability = build_offset_suitability(
            project
        )

        factor = next(
            factor
            for factor in suitability.factors
            if factor.key == "project_type_available"
        )

        self.assertTrue(factor.matched)

    def test_explicit_project_type_preference_can_match(self):
        project = self.make_project(
            project_type="Renewable Energy"
        )

        suitability = build_offset_suitability(
            project,
            preferred_project_types=[
                "Renewable Energy"
            ],
        )

        factor = next(
            factor
            for factor in suitability.factors
            if factor.key == "preferred_project_type"
        )

        self.assertTrue(factor.matched)

    def test_preference_is_not_invented_when_not_provided(self):
        project = self.make_project()

        suitability = build_offset_suitability(
            project
        )

        self.assertNotIn(
            "preferred_project_type",
            {
                factor.key
                for factor in suitability.factors
            },
        )

    def test_existing_score_is_preserved(self):
        project = self.make_project()

        suitability = build_offset_suitability(
            project,
            score=Decimal("91.25"),
        )

        self.assertEqual(
            suitability.score,
            Decimal("91.25"),
        )

    def test_matched_factor_count_is_consistent(self):
        project = self.make_project()

        suitability = build_offset_suitability(
            project
        )

        expected_count = sum(
            factor.matched
            for factor in suitability.factors
        )

        self.assertEqual(
            suitability.matched_factor_count,
            expected_count,
        )