from __future__ import annotations

from collections import defaultdict

from django.core.management.base import BaseCommand
from django.db.models.functions import TruncMonth

from carbon.models import CarbonActivity
from ml.training.random_forest import (
    MINIMUM_TRANSITIONS,
    MINIMUM_USERS,
)


class Command(BaseCommand):
    """
    Display the current CarbonIQ ML training-data readiness.
    """

    help = (
        "Display CarbonIQ machine-learning data readiness "
        "for Random Forest training."
    )

    def handle(self, *args, **options):
        queryset = (
            CarbonActivity.objects
            .filter(
                status=CarbonActivity.Status.COMPLETED,
                carbon_footprint__isnull=False,
            )
            .annotate(
                month=TruncMonth("created_at"),
            )
            .values(
                "user_id",
                "month",
            )
            .distinct()
        )

        months_by_user = defaultdict(set)

        for record in queryset:
            months_by_user[record["user_id"]].add(
                record["month"].date().replace(day=1)
            )

        completed_submission_count = (
            CarbonActivity.objects
            .filter(
                status=CarbonActivity.Status.COMPLETED,
                carbon_footprint__isnull=False,
            )
            .count()
        )

        distinct_user_count = len(months_by_user)

        transition_count = 0

        for months in months_by_user.values():
            month_keys = {
                month.year * 12 + month.month
                for month in months
            }

            for month in months:
                current_key = (
                    month.year * 12 + month.month
                )

                if current_key + 1 in month_keys:
                    transition_count += 1

        transitions_ready = (
            transition_count >= MINIMUM_TRANSITIONS
        )

        users_ready = (
            distinct_user_count >= MINIMUM_USERS
        )

        is_ready = (
            transitions_ready
            and users_ready
        )

        self.stdout.write("")
        self.stdout.write(
            self.style.NOTICE(
                "CarbonIQ ML Data Status"
            )
        )
        self.stdout.write(
            self.style.NOTICE(
                "-----------------------"
            )
        )

        self.stdout.write(
            f"Completed submissions : "
            f"{completed_submission_count}"
        )

        self.stdout.write(
            f"Distinct users        : "
            f"{distinct_user_count}"
        )

        self.stdout.write(
            f"Temporal transitions  : "
            f"{transition_count}"
        )

        self.stdout.write("")

        self.stdout.write(
            f"Minimum transitions   : "
            f"{MINIMUM_TRANSITIONS}"
        )

        self.stdout.write(
            f"Minimum users         : "
            f"{MINIMUM_USERS}"
        )

        self.stdout.write("")

        if is_ready:
            self.stdout.write(
                self.style.SUCCESS(
                    "Status                : READY"
                )
            )
        else:
            self.stdout.write(
                self.style.WARNING(
                    "Status                : NOT READY"
                )
            )

            reasons = []

            if not transitions_ready:
                reasons.append(
                    "insufficient temporal training transitions"
                )

            if not users_ready:
                reasons.append(
                    "insufficient distinct users"
                )

            self.stdout.write(
                "Reason                : "
                + "; ".join(reasons)
            )