from datetime import date
from decimal import Decimal
from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
)


class MLDataStatusCommandTests(TestCase):
    """Tests for the ml_data_status management command."""

    @classmethod
    def setUpTestData(cls):
        cls.user_one = CustomUser.objects.create_user(
            email="status_user1@example.com",
            full_name="Status User One",
            password="TestPassword123!",
        )

        cls.user_two = CustomUser.objects.create_user(
            email="status_user2@example.com",
            full_name="Status User Two",
            password="TestPassword123!",
        )

        cls.electricity = ActivityCategory.objects.create(
            name="Electricity",
            unit="kWh",
            is_active=True,
            display_order=1,
        )

        cls.factor = EmissionFactor.objects.create(
            activity_category=cls.electricity,
            factor=Decimal("0.7000"),
            source="Test Source",
            effective_from=date(2026, 1, 1),
            is_active=True,
        )

    def create_completed_activity(
        self,
        user,
        year,
        month,
        day=15,
    ):
        """Create a valid completed CarbonIQ activity."""

        activity = CarbonActivity.objects.create(
            user=user,
            status=CarbonActivity.Status.COMPLETED,
        )

        # CarbonActivity.created_at uses auto_now_add, so set the
        # desired historical timestamp after creation.
        activity.created_at = activity.created_at.replace(
            year=year,
            month=month,
            day=day,
        )

        activity.save(
            update_fields=["created_at"],
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.factor,
            quantity=Decimal("100.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("70.00"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("70.00"),
        )

        return activity

    def create_failed_activity(
        self,
        user,
        year,
        month,
        day=15,
    ):
        """Create a failed activity that must be ignored."""

        activity = CarbonActivity.objects.create(
            user=user,
            status=CarbonActivity.Status.FAILED,
        )

        activity.created_at = activity.created_at.replace(
            year=year,
            month=month,
            day=day,
        )

        activity.save(
            update_fields=["created_at"],
        )

        ActivityEntry.objects.create(
            carbon_activity=activity,
            category=self.electricity,
            emission_factor=self.factor,
            quantity=Decimal("9999.00"),
            emission_factor_snapshot=Decimal("0.7000"),
            entry_emission=Decimal("6999.30"),
        )

        CarbonFootprint.objects.create(
            carbon_activity=activity,
            total_emission=Decimal("6999.30"),
        )

        return activity

    def test_no_data_reports_not_ready(self):
        output = StringIO()

        call_command(
            "ml_data_status",
            stdout=output,
        )

        output_text = output.getvalue()

        self.assertIn(
            "Completed submissions : 0",
            output_text,
        )

        self.assertIn(
            "Distinct users        : 0",
            output_text,
        )

        self.assertIn(
            "Temporal transitions  : 0",
            output_text,
        )

        self.assertIn(
            "Status                : NOT READY",
            output_text,
        )

    def test_two_users_without_next_month_are_not_ready(self):
        self.create_completed_activity(
            self.user_one,
            2026,
            1,
        )

        self.create_completed_activity(
            self.user_two,
            2026,
            1,
        )

        output = StringIO()

        call_command(
            "ml_data_status",
            stdout=output,
        )

        output_text = output.getvalue()

        self.assertIn(
            "Completed submissions : 2",
            output_text,
        )

        self.assertIn(
            "Distinct users        : 2",
            output_text,
        )

        self.assertIn(
            "Temporal transitions  : 0",
            output_text,
        )

        self.assertIn(
            "Status                : NOT READY",
            output_text,
        )

    def test_consecutive_month_creates_one_transition(self):
        self.create_completed_activity(
            self.user_one,
            2026,
            1,
        )

        self.create_completed_activity(
            self.user_one,
            2026,
            2,
        )

        output = StringIO()

        call_command(
            "ml_data_status",
            stdout=output,
        )

        output_text = output.getvalue()

        self.assertIn(
            "Temporal transitions  : 1",
            output_text,
        )

        self.assertIn(
            "Status                : NOT READY",
            output_text,
        )

    def test_failed_submission_is_ignored(self):
        self.create_completed_activity(
            self.user_one,
            2026,
            1,
        )

        self.create_completed_activity(
            self.user_one,
            2026,
            2,
        )

        self.create_failed_activity(
            self.user_two,
            2026,
            1,
        )

        self.create_failed_activity(
            self.user_two,
            2026,
            2,
        )

        output = StringIO()

        call_command(
            "ml_data_status",
            stdout=output,
        )

        output_text = output.getvalue()

        self.assertIn(
            "Completed submissions : 2",
            output_text,
        )

        self.assertIn(
            "Distinct users        : 1",
            output_text,
        )

        self.assertIn(
            "Temporal transitions  : 1",
            output_text,
        )

    def test_missing_month_does_not_create_transition(self):
        self.create_completed_activity(
            self.user_one,
            2026,
            1,
        )

        self.create_completed_activity(
            self.user_one,
            2026,
            3,
        )

        output = StringIO()

        call_command(
            "ml_data_status",
            stdout=output,
        )

        output_text = output.getvalue()

        self.assertIn(
            "Completed submissions : 2",
            output_text,
        )

        self.assertIn(
            "Temporal transitions  : 0",
            output_text,
        )

        self.assertIn(
            "Status                : NOT READY",
            output_text,
        )

    def test_multiple_submissions_same_month_do_not_create_multiple_transitions(
        self,
    ):
        self.create_completed_activity(
            self.user_one,
            2026,
            1,
            day=5,
        )

        self.create_completed_activity(
            self.user_one,
            2026,
            1,
            day=20,
        )

        self.create_completed_activity(
            self.user_one,
            2026,
            2,
        )

        output = StringIO()

        call_command(
            "ml_data_status",
            stdout=output,
        )

        output_text = output.getvalue()

        self.assertIn(
            "Completed submissions : 3",
            output_text,
        )

        self.assertIn(
            "Temporal transitions  : 1",
            output_text,
        )
