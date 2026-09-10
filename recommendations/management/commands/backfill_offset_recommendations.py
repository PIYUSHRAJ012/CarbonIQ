from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from carbon.models import CarbonActivity
from recommendations.models import OffsetRecommendation
from recommendations.services.offset_recommendations import (
    OffsetRecommendationError,
    generate_offset_recommendations,
)


class Command(BaseCommand):
    help = (
        "Backfill offset-project recommendations for existing "
        "CarbonIQ users with completed carbon footprints."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help=(
                "Regenerate offset recommendations even when "
                "active recommendations already exist."
            ),
        )

    def handle(self, *args, **options):
        eligible_users = (
            CustomUser.objects
            .filter(
                carbon_activities__status=CarbonActivity.Status.COMPLETED,
                carbon_activities__carbon_footprint__isnull=False,
            )
            .distinct()
            .order_by("id")
        )

        generated_count = 0
        skipped_count = 0
        failed_count = 0

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "CarbonIQ Offset Recommendation Backfill"
            )
        )
        self.stdout.write("=" * 55)

        if options["refresh"]:
            self.stdout.write(
                "Mode              : REFRESH"
            )
        else:
            self.stdout.write(
                "Mode              : BACKFILL"
            )

        for user in eligible_users:
            has_active_recommendations = (
                OffsetRecommendation.objects.filter(
                    user=user,
                    status=OffsetRecommendation.Status.ACTIVE,
                ).exists()
            )

            if (
                has_active_recommendations
                and not options["refresh"]
            ):
                skipped_count += 1

                self.stdout.write(
                    f"SKIPPED  {user.email} "
                    "(active recommendations already exist)"
                )
                continue

            try:
                generated = generate_offset_recommendations(user)

                if generated:
                    generated_count += 1

                    self.stdout.write(
                        self.style.SUCCESS(
                            f"GENERATED {user.email} "
                            f"({len(generated)} recommendations)"
                        )
                    )
                else:
                    skipped_count += 1

                    self.stdout.write(
                        f"SKIPPED  {user.email} "
                        "(no eligible offset recommendations)"
                    )

            except OffsetRecommendationError as exc:
                failed_count += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"FAILED   {user.email}: {exc}"
                    )
                )

            except Exception as exc:
                failed_count += 1

                self.stdout.write(
                    self.style.ERROR(
                        f"FAILED   {user.email}: {exc}"
                    )
                )

        self.stdout.write("")
        self.stdout.write("=" * 55)
        self.stdout.write(
            f"Eligible users : {eligible_users.count()}"
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Generated users: {generated_count}"
            )
        )
        self.stdout.write(
            f"Skipped users  : {skipped_count}"
        )
        self.stdout.write(
            self.style.ERROR(
                f"Failed users   : {failed_count}"
            )
        )