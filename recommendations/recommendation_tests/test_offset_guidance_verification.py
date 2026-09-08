from datetime import timedelta

from django.test import TestCase
from django.utils import timezone

from recommendations.models import OffsetProject
from recommendations.services.offset_guidance.verification import (
    VerificationState,
    build_offset_verification,
    get_verification_state,
)


class OffsetGuidanceVerificationTests(TestCase):

    def setUp(self):
        self.project = OffsetProject.objects.create(
            name="India Solar Project",
            description="Solar renewable energy project.",
            project_type="Renewable Energy",
            country="India",
            registry="Gold Standard",
            registry_project_id="GS-E9-TEST-001",
            registry_url=(
                "https://example.com/gs-e9-test-001"
            ),
            status=OffsetProject.ProjectStatus.ACTIVE,
            sdg_impacts=[
                {"sdg": 13},
                {"sdg": 7},
            ],
            certification_documents_url=(
                "https://example.com/gs-e9-documents"
            ),
            source_last_verified_at=timezone.now(),
            is_active=True,
        )

    def test_missing_verification_date_is_unavailable(self):
        state, label, age = get_verification_state(
            None
        )

        self.assertEqual(
            state,
            VerificationState.UNAVAILABLE,
        )
        self.assertEqual(
            label,
            "Verification date unavailable",
        )
        self.assertIsNone(age)

    def test_recent_verification_is_fresh(self):
        now = timezone.now()

        state, label, age = get_verification_state(
            now - timedelta(days=10),
            now=now,
        )

        self.assertEqual(
            state,
            VerificationState.FRESH,
        )
        self.assertEqual(
            label,
            "Recently verified",
        )
        self.assertEqual(
            age,
            10,
        )

    def test_boundary_at_30_days_is_fresh(self):
        now = timezone.now()

        state, _, age = get_verification_state(
            now - timedelta(days=30),
            now=now,
        )

        self.assertEqual(
            state,
            VerificationState.FRESH,
        )
        self.assertEqual(
            age,
            30,
        )

    def test_boundary_at_31_days_is_aging(self):
        now = timezone.now()

        state, _, age = get_verification_state(
            now - timedelta(days=31),
            now=now,
        )

        self.assertEqual(
            state,
            VerificationState.AGING,
        )
        self.assertEqual(
            age,
            31,
        )

    def test_boundary_at_90_days_is_aging(self):
        now = timezone.now()

        state, _, age = get_verification_state(
            now - timedelta(days=90),
            now=now,
        )

        self.assertEqual(
            state,
            VerificationState.AGING,
        )
        self.assertEqual(
            age,
            90,
        )

    def test_more_than_90_days_is_stale(self):
        now = timezone.now()

        state, label, age = get_verification_state(
            now - timedelta(days=91),
            now=now,
        )

        self.assertEqual(
            state,
            VerificationState.STALE,
        )
        self.assertEqual(
            label,
            "Verification is old",
        )
        self.assertEqual(
            age,
            91,
        )

    def test_build_verification_exposes_traceability_fields(self):
        verification = build_offset_verification(
            self.project
        )

        self.assertEqual(
            verification.registry,
            "Gold Standard",
        )

        self.assertEqual(
            verification.registry_project_id,
            "GS-E9-TEST-001",
        )

        self.assertEqual(
            verification.registry_url,
            "https://example.com/gs-e9-test-001",
        )

        self.assertEqual(
            verification.project_status,
            OffsetProject.ProjectStatus.ACTIVE,
        )

        self.assertTrue(
            verification.has_certification_documents
        )

        self.assertEqual(
            verification.state,
            VerificationState.FRESH,
        )

    def test_unknown_project_status_does_not_crash(self):
        verification = build_offset_verification(
            self.project
        )

        verification = verification.__class__(
            registry=verification.registry,
            registry_project_id=(
                verification.registry_project_id
            ),
            registry_url=verification.registry_url,
            certification_documents_url=(
                verification.certification_documents_url
            ),
            source_last_verified_at=(
                verification.source_last_verified_at
            ),
            project_status="UNEXPECTED_STATUS",
            state=verification.state,
            state_label=verification.state_label,
            days_since_verification=(
                verification.days_since_verification
            ),
        )

        self.assertEqual(
            verification.status_label,
            "UNEXPECTED_STATUS",
        )