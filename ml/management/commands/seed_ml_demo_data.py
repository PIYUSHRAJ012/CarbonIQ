from datetime import date

from django.core.management.base import BaseCommand, CommandError

from ml.services.demo_data import (
    DEMO_MONTH_COUNT,
    DEMO_USER_COUNT,
    DEMO_PASSWORD,
    seed_demo_dataset,
)


class Command(BaseCommand):
    help = (
        "Generate a synthetic CarbonIQ dataset for "
        "demonstrating Random Forest prediction and K-Means segmentation."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--reset",
            action="store_true",
            help="Delete existing CarbonIQ demo users before generating data.",
        )

        parser.add_argument(
            "--users",
            type=int,
            default=DEMO_USER_COUNT,
            help=(
                "Number of synthetic demo users to create "
                "(minimum 10)."
            ),
        )

        parser.add_argument(
            "--months",
            type=int,
            default=DEMO_MONTH_COUNT,
            help=(
                "Number of consecutive historical months "
                "to generate (minimum 2)."
            ),
        )

    def handle(self, *args, **options):
        user_count = options["users"]
        month_count = options["months"]
        reset = options["reset"]

        if user_count < 10:
            raise CommandError(
                "The number of demo users must be at least 10."
            )

        if month_count < 2:
            raise CommandError(
                "The number of demo months must be at least 2."
            )

        self.stdout.write(
            self.style.NOTICE(
                "Generating CarbonIQ synthetic ML demo dataset..."
            )
        )

        try:
            summary = seed_demo_dataset(
                user_count=user_count,
                month_count=month_count,
                start_period=date(2025, 10, 1),
                reset=reset,
            )
        except Exception as exc:
            raise CommandError(
                f"Demo dataset generation failed: {exc}"
            ) from exc

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "CarbonIQ ML demo dataset generated successfully."
            )
        )

        self.stdout.write(
            f"Deleted demo users : {summary['deleted_users']}"
        )
        self.stdout.write(
            f"Created demo users : {summary['created_users']}"
        )
        self.stdout.write(
            f"Reused demo users  : {summary['reused_users']}"
        )
        self.stdout.write(
            f"Submissions created: {summary['submissions_created']}"
        )
        self.stdout.write(
            f"Activity entries   : {summary['entries_created']}"
        )
        self.stdout.write(
            f"Users              : {summary['user_count']}"
        )
        self.stdout.write(
            f"Months             : {summary['month_count']}"
        )
        self.stdout.write(
            f"Start period       : {summary['start_period']:%Y-%m}"
        )
        self.stdout.write(
            f"End period         : {summary['end_period']:%Y-%m}"
        )
        self.stdout.write("")
        self.stdout.write(
            f"Demo password      : {DEMO_PASSWORD}"
        )