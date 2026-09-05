from decimal import Decimal

from django.core.exceptions import ValidationError
from django.core.management import call_command
from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import ActivityCategory, CarbonActivity
from carbon.services.submission import CarbonSubmissionService


class CarbonSubmissionServiceTests(TestCase):
    """
    Tests for CarbonSubmissionService.
    """

    @classmethod
    def setUpTestData(cls):
        # Populate the same default categories and emission factors
        # used by the real application.
        call_command("seed_initial_data", verbosity=0)

        cls.user = CustomUser.objects.create_user(
            email="submission@test.com",
            full_name="Submission Test User",
            password="TestPassword123!",
        )

        cls.electricity = ActivityCategory.objects.get(
            name="Electricity"
        )

        cls.transportation = ActivityCategory.objects.get(
            name="Transportation"
        )

        # Category deliberately has no emission factor.
        cls.no_factor_category = ActivityCategory.objects.create(
            name="Test Failure Category",
            description="Used to test calculation failure.",
            unit="unit",
            display_order=999,
            is_active=True,
        )

    def test_successful_multiple_activity_submission(self):
        entries_data = [
            {
                "category": self.electricity,
                "quantity": Decimal("100.00"),
            },
            {
                "category": self.transportation,
                "quantity": Decimal("50.00"),
            },
        ]

        activity = CarbonSubmissionService.create_submission(
            user=self.user,
            entries_data=entries_data,
        )

        activity.refresh_from_db()

        self.assertEqual(
            activity.status,
            CarbonActivity.Status.COMPLETED,
        )

        self.assertEqual(activity.entries.count(), 2)

        self.assertTrue(
            hasattr(activity, "carbon_footprint")
        )

        footprint = activity.carbon_footprint

        self.assertEqual(
            footprint.total_emission,
            sum(
                entry.entry_emission
                for entry in activity.entries.all()
            ),
        )

    def test_emission_factor_snapshots_are_stored(self):
        entries_data = [
            {
                "category": self.electricity,
                "quantity": Decimal("100.00"),
            },
            {
                "category": self.transportation,
                "quantity": Decimal("50.00"),
            },
        ]

        activity = CarbonSubmissionService.create_submission(
            user=self.user,
            entries_data=entries_data,
        )

        for entry in activity.entries.select_related(
            "emission_factor"
        ):
            self.assertIsNotNone(
                entry.emission_factor
            )

            self.assertIsNotNone(
                entry.emission_factor_snapshot
            )

            self.assertEqual(
                entry.emission_factor_snapshot,
                entry.emission_factor.factor,
            )

            self.assertIsNotNone(
                entry.entry_emission
            )

    def test_failed_submission_is_rolled_back(self):
        initial_count = CarbonActivity.objects.count()

        entries_data = [
            {
                "category": self.electricity,
                "quantity": Decimal("100.00"),
            },
            {
                "category": self.no_factor_category,
                "quantity": Decimal("50.00"),
            },
        ]

        with self.assertRaises(Exception):
            CarbonSubmissionService.create_submission(
                user=self.user,
                entries_data=entries_data,
            )

        self.assertEqual(
            CarbonActivity.objects.count(),
            initial_count,
        )