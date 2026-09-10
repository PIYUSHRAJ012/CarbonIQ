from datetime import datetime
from decimal import Decimal

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from recommendations.models import OffsetProject
from recommendations.services.offset_scoring import (
    calculate_domain_score,
    calculate_geography_score,
    calculate_offset_project_score,
    calculate_offset_requirement,
    calculate_project_type_score,
    rank_offset_projects,
)
from recommendations.services.signals import RecommendationSignals


class OffsetScoringTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="offset@example.com",
            full_name="Offset User",
            password="test-password-123",
        )

        self.signals = RecommendationSignals(
            total_emission=Decimal("2500.0000"),

            category_emissions=(
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("1500.0000"),
                },
                {
                    "category__name": "Transportation",
                    "total_emission": Decimal("1000.0000"),
                },
            ),

            monthly_emissions=(
                {
                    "month": datetime(
                        2026,
                        7,
                        1,
                    ),
                    "total_emission": Decimal("700.0000"),
                },
                {
                    "month": datetime(
                        2026,
                        8,
                        1,
                    ),
                    "total_emission": Decimal("840.0000"),
                },
            ),

            weekly_emissions=(),

            top_category="Electricity",

            top_category_emission=Decimal(
                "1500.0000"
            ),

            dominant_domain="energy",
        )

        self.india_project = OffsetProject.objects.create(
            name="India Solar Renewable Energy Project",
            description=(
                "Solar renewable energy project generating "
                "clean electricity."
            ),
            project_type="Renewable Energy",
            country="India",
            region="",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-001",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-001"
            ),
            standard="",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Large",
            annual_estimated_credits=Decimal(
                "10000.00"
            ),
            sdg_impacts=[
                {"sdg": 7},
                {"sdg": 13},
            ],
            project_developer="Example Energy Ltd.",
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        self.foreign_project = OffsetProject.objects.create(
            name="Brazil Forest Restoration Project",
            description=(
                "Forest restoration and reforestation project."
            ),
            project_type="A/R",
            country="Brazil",
            region="",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-002",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-002"
            ),
            standard="",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Medium",
            annual_estimated_credits=Decimal(
                "5000.00"
            ),
            sdg_impacts=[
                {"sdg": 13},
            ],
            project_developer="Example Forest Ltd.",
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

    # -------------------------------------------------------------
    # Offset requirement
    # -------------------------------------------------------------

    def test_calculates_requirement_from_latest_month(self):
        requirement = calculate_offset_requirement(
            self.signals
        )

        self.assertIsNotNone(
            requirement
        )

        self.assertEqual(
            requirement.latest_month_emission_kg,
            Decimal("840.0000"),
        )

        self.assertEqual(
            requirement.indicative_tonnes,
            Decimal("0.8400"),
        )

        self.assertEqual(
            requirement.source,
            "latest_completed_month",
        )

        self.assertEqual(
            requirement.source_month,
            datetime(
                2026,
                8,
                1,
            ),
        )

    def test_requirement_does_not_use_lifetime_total(self):
        requirement = calculate_offset_requirement(
            self.signals
        )

        self.assertIsNotNone(
            requirement
        )

        self.assertNotEqual(
            requirement.latest_month_emission_kg,
            self.signals.total_emission,
        )

        self.assertEqual(
            requirement.indicative_tonnes,
            Decimal("0.8400"),
        )

    def test_missing_monthly_emissions_returns_none(self):
        signals = RecommendationSignals(
            total_emission=Decimal("5000.0000"),
            category_emissions=(),
            monthly_emissions=(),
            weekly_emissions=(),
            top_category=None,
            top_category_emission=Decimal("0.0000"),
        )

        requirement = calculate_offset_requirement(
            signals
        )

        self.assertIsNone(
            requirement
        )

    def test_zero_latest_month_returns_none(self):
        signals = RecommendationSignals(
            total_emission=Decimal("1000.0000"),
            category_emissions=(),
            monthly_emissions=(
                {
                    "month": datetime(
                        2026,
                        8,
                        1,
                    ),
                    "total_emission": Decimal("0.0000"),
                },
            ),
            weekly_emissions=(),
            top_category=None,
            top_category_emission=Decimal("0.0000"),
        )

        requirement = calculate_offset_requirement(
            signals
        )

        self.assertIsNone(
            requirement
        )

    # -------------------------------------------------------------
    # Domain scoring
    # -------------------------------------------------------------

    def test_energy_project_matches_energy_domain(self):
        score = calculate_domain_score(
            self.india_project,
            self.signals,
        )

        self.assertEqual(
            score,
            Decimal("75"),
        )

    def test_unmatched_project_domain_gets_lower_score(self):
        score = calculate_domain_score(
            self.foreign_project,
            self.signals,
        )

        self.assertEqual(
            score,
            Decimal("25"),
        )

    def test_no_user_domain_returns_neutral_score(self):
        signals = RecommendationSignals(
            total_emission=Decimal("1000.0000"),
            category_emissions=(),
            monthly_emissions=(),
            weekly_emissions=(),
            top_category=None,
            top_category_emission=Decimal("0.0000"),
            dominant_domain=None,
        )

        project = OffsetProject.objects.create(
            name="Generic Offset Project",
            project_type="Other",
            country="India",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-003",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-003"
            ),
            status=OffsetProject.ProjectStatus.ACTIVE,
            sdg_impacts=[],
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        score = calculate_domain_score(
            project,
            signals,
        )

        self.assertEqual(
            score,
            Decimal("50"),
        )
    # -------------------------------------------------------------
    # Project-type scoring
    # -------------------------------------------------------------

    def test_direct_project_type_match_gets_full_score(self):
        project = OffsetProject.objects.create(
            name="India Solar PV Project",
            description="Solar photovoltaic electricity project.",
            project_type="PV",
            country="India",
            region="",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-004",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-004"
            ),
            standard="",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Large",
            annual_estimated_credits=Decimal(
                "10000.00"
            ),
            sdg_impacts=[
                {"sdg": 13},
            ],
            project_developer="Example Solar Ltd.",
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        electricity_only_signals = RecommendationSignals(
            total_emission=Decimal("1500.0000"),
            category_emissions=(
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("1500.0000"),
                },
            ),
            monthly_emissions=self.signals.monthly_emissions,
            weekly_emissions=self.signals.weekly_emissions,
            top_category="Electricity",
            top_category_emission=Decimal("1500.0000"),
            dominant_domain=None,
        )

        score = calculate_project_type_score(
            project,
            electricity_only_signals,
        )

        self.assertEqual(
            score,
            Decimal("100"),
        )

    def test_unrelated_project_type_gets_lower_score(self):
        score = calculate_project_type_score(
            self.foreign_project,
            self.signals,
        )

        self.assertEqual(
            score,
            Decimal("25"),
        )

    def test_unknown_project_type_gets_neutral_score(self):
        project = OffsetProject.objects.create(
            name="Generic Offset Project",
            project_type="Other",
            country="India",
            region="",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-005",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-005"
            ),
            standard="",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Medium",
            annual_estimated_credits=Decimal(
                "5000.00"
            ),
            sdg_impacts=[],
            project_developer="Example Developer",
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        score = calculate_project_type_score(
            project,
            self.signals,
        )

        self.assertEqual(
            score,
            Decimal("50"),
        )
    # -------------------------------------------------------------
    # Geography scoring
    # -------------------------------------------------------------

    def test_india_project_gets_full_geographic_score(self):
        score = calculate_geography_score(
            self.india_project,
            self.user,
        )

        self.assertEqual(
            score,
            Decimal("100"),
        )

    def test_non_india_project_gets_lower_geographic_score(self):
        score = calculate_geography_score(
            self.foreign_project,
            self.user,
        )

        self.assertEqual(
            score,
            Decimal("40"),
        )

    # -------------------------------------------------------------
    # Complete project scoring
    # -------------------------------------------------------------

    def test_active_india_project_is_applicable(self):
        result = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        self.assertTrue(
            result.applicable
        )

        self.assertGreater(
            result.score,
            Decimal("0"),
        )

    def test_inactive_project_is_not_applicable(self):
        self.india_project.is_active = False
        self.india_project.save(
            update_fields=["is_active"]
        )

        result = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        self.assertFalse(
            result.applicable
        )

        self.assertEqual(
            result.score,
            Decimal("0.0000"),
        )

    def test_suspended_project_is_not_applicable(self):
        self.india_project.status = (
            OffsetProject.ProjectStatus.SUSPENDED
        )
        self.india_project.save(
            update_fields=["status"]
        )

        result = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        self.assertFalse(
            result.applicable
        )

        self.assertEqual(
            result.score,
            Decimal("0.0000"),
        )

    def test_sdg_13_gets_full_sdg_score(self):
        result = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        self.assertEqual(
            result.sdg_score,
            Decimal("100"),
        )

    def test_project_score_stays_between_zero_and_hundred(
        self,
    ):
        result = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        self.assertGreaterEqual(
            result.score,
            Decimal("0"),
        )

        self.assertLessEqual(
            result.score,
            Decimal("100"),
        )

    def test_india_energy_project_scores_higher_than_foreign_forest_project(
        self,
    ):
        india_result = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        foreign_result = calculate_offset_project_score(
            self.foreign_project,
            self.signals,
            self.user,
        )

        self.assertGreater(
            india_result.score,
            foreign_result.score,
        )

    def test_direct_project_type_match_outscores_text_only_match(self):
        text_match = calculate_offset_project_score(
            self.india_project,
            self.signals,
            self.user,
        )

        direct_match_project = OffsetProject.objects.create(
            name="India PV Renewable Electricity Project",
            description=(
                "Solar photovoltaic renewable electricity "
                "project generating clean electricity."
            ),
            project_type="PV",
            country="India",
            region="",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-006",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-006"
            ),
            standard="",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Large",
            annual_estimated_credits=Decimal(
                "10000.00"
            ),
            sdg_impacts=[
                {"sdg": 13},
            ],
            project_developer="Example Solar Ltd.",
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        direct_match = calculate_offset_project_score(
            direct_match_project,
            self.signals,
            self.user,
        )

        self.assertGreater(
            direct_match.score,
            text_match.score,
        )
    # -------------------------------------------------------------
    # Ranking
    # -------------------------------------------------------------

    def test_ranked_results_put_higher_score_first(self):
        results = rank_offset_projects(
            [
                self.foreign_project,
                self.india_project,
            ],
            self.signals,
            self.user,
        )

        self.assertEqual(
            results[0].project,
            self.india_project,
        )

        self.assertEqual(
            results[1].project,
            self.foreign_project,
        )

    def test_ranking_is_deterministic(self):
        first = rank_offset_projects(
            [
                self.foreign_project,
                self.india_project,
            ],
            self.signals,
            self.user,
        )

        second = rank_offset_projects(
            [
                self.foreign_project,
                self.india_project,
            ],
            self.signals,
            self.user,
        )

        self.assertEqual(
            [
                result.project.id
                for result in first
            ],
            [
                result.project.id
                for result in second
            ],
        )

    def test_non_applicable_project_gets_zero_score_in_ranking(
        self,
    ):
        self.foreign_project.is_active = False
        self.foreign_project.save(
            update_fields=["is_active"]
        )

        results = rank_offset_projects(
            [
                self.foreign_project,
                self.india_project,
            ],
            self.signals,
            self.user,
        )

        self.assertEqual(
            results[1].score,
            Decimal("0.0000"),
        )

        self.assertFalse(
            results[1].applicable
        )

    def test_project_type_score_uses_full_category_distribution(self):
        score = calculate_project_type_score(
            self.india_project,
            self.signals,
        )

        # Electricity is the dominant category, but the user's
        # other categories must also influence the score.
        self.assertLess(
            score,
            Decimal("100"),
        )


    def test_project_type_score_uses_category_emission_distribution(self):
        mixed_signals = RecommendationSignals(
            total_emission=Decimal("2500.0000"),
            category_emissions=(
                {
                    "category__name": "Electricity",
                    "total_emission": Decimal("800.0000"),
                },
                {
                    "category__name": "Transportation",
                    "total_emission": Decimal("1200.0000"),
                },
            ),
            monthly_emissions=self.signals.monthly_emissions,
            weekly_emissions=self.signals.weekly_emissions,
            top_category="Transportation",
            top_category_emission=Decimal("1200.0000"),
            dominant_domain=None,
        )

        transport_project = OffsetProject.objects.create(
            name="India Transport Efficiency Project",
            description=(
                "Transport energy efficiency project."
            ),
            project_type="Energy Efficiency - Transport Sector",
            country="India",
            region="",
            registry="Gold Standard",
            registry_project_id="GS-OFFSET-007",
            registry_url=(
                "https://registry.goldstandard.org/"
                "projects/details/offset-007"
            ),
            standard="",
            status=OffsetProject.ProjectStatus.ACTIVE,
            project_scale="Large",
            annual_estimated_credits=Decimal(
                "10000.00"
            ),
            sdg_impacts=[
                {"sdg": 13},
            ],
            project_developer="Example Transport Ltd.",
            certification_documents_url="",
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

        score = calculate_project_type_score(
            transport_project,
            mixed_signals,
        )

        self.assertEqual(
            score,
            Decimal("70.0000"),
        )