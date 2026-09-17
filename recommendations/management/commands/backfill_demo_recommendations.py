from __future__ import annotations

from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from recommendations.models import (
    OffsetRecommendation,
    UserRecommendation,
)
from recommendations.services.engine import (
    generate_user_recommendations,
)
from recommendations.services.offset_recommendations import (
    OffsetRecommendationError,
    generate_offset_recommendations,
)


class Command(BaseCommand):
    help = (
        "Generate sustainability and offset recommendations "
        "for CarbonIQ synthetic demo users."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--refresh",
            action="store_true",
            help=(
                "Regenerate recommendations even when active "
                "recommendations already exist."
            ),
        )

    def handle(self, *args, **options):
        refresh = options["refresh"]

        demo_users = (
            CustomUser.objects
            .filter(
                email__startswith="demo_user_",
                email__endswith="@demo.carboniq.local",
            )
            .order_by("id")
        )

        sustainability_generated = 0
        sustainability_skipped = 0
        sustainability_failed = 0

        offset_generated = 0
        offset_skipped = 0
        offset_failed = 0

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "CarbonIQ Demo Recommendation Backfill"
            )
        )
        self.stdout.write("=" * 60)
        self.stdout.write(
            f"Mode          : "
            f"{'REFRESH' if refresh else 'BACKFILL'}"
        )
        self.stdout.write(
            f"Demo users    : {demo_users.count()}"
        )
        self.stdout.write("")

        for user in demo_users:
            self.stdout.write(
                self.style.NOTICE(
                    f"Processing {user.email}"
                )
            )

            # ---------------------------------------------------------
            # Sustainability recommendations
            # ---------------------------------------------------------
            has_sustainability = (
                UserRecommendation.objects.filter(
                    user=user,
                    status=UserRecommendation.Status.ACTIVE,
                ).exists()
            )

            if has_sustainability and not refresh:
                sustainability_skipped += 1

                self.stdout.write(
                    "  Sustainability : SKIPPED "
                    "(active recommendations already exist)"
                )
            else:
                try:
                    generated = generate_user_recommendations(user)

                    sustainability_generated += len(generated)

                    self.stdout.write(
                        self.style.SUCCESS(
                            "  Sustainability : GENERATED "
                            f"({len(generated)})"
                        )
                    )

                except Exception as exc:
                    sustainability_failed += 1

                    self.stdout.write(
                        self.style.ERROR(
                            "  Sustainability : FAILED "
                            f"({exc})"
                        )
                    )

            # ---------------------------------------------------------
            # Offset recommendations
            # ---------------------------------------------------------
            has_offsets = (
                OffsetRecommendation.objects.filter(
                    user=user,
                    status=OffsetRecommendation.Status.ACTIVE,
                ).exists()
            )

            if has_offsets and not refresh:
                offset_skipped += 1

                self.stdout.write(
                    "  Offset         : SKIPPED "
                    "(active recommendations already exist)"
                )
            else:
                try:
                    generated = generate_offset_recommendations(user)

                    offset_generated += len(generated)

                    self.stdout.write(
                        self.style.SUCCESS(
                            "  Offset         : GENERATED "
                            f"({len(generated)})"
                        )
                    )

                except OffsetRecommendationError as exc:
                    offset_failed += 1

                    self.stdout.write(
                        self.style.ERROR(
                            "  Offset         : FAILED "
                            f"({exc})"
                        )
                    )

                except Exception as exc:
                    offset_failed += 1

                    self.stdout.write(
                        self.style.ERROR(
                            "  Offset         : FAILED "
                            f"({exc})"
                        )
                    )

            self.stdout.write("")

        # -------------------------------------------------------------
        # Summary
        # -------------------------------------------------------------
        self.stdout.write("=" * 60)

        self.stdout.write(
            f"Sustainability generated : "
            f"{sustainability_generated}"
        )

        self.stdout.write(
            f"Sustainability skipped   : "
            f"{sustainability_skipped}"
        )

        self.stdout.write(
            f"Sustainability failed    : "
            f"{sustainability_failed}"
        )

        self.stdout.write("")

        self.stdout.write(
            f"Offset generated         : "
            f"{offset_generated}"
        )

        self.stdout.write(
            f"Offset skipped           : "
            f"{offset_skipped}"
        )

        self.stdout.write(
            f"Offset failed            : "
            f"{offset_failed}"
        )

        self.stdout.write("")

        total_failures = (
            sustainability_failed
            + offset_failed
        )

        if total_failures:
            self.stdout.write(
                self.style.WARNING(
                    f"Completed with {total_failures} failure(s)."
                )
            )
        else:
            self.stdout.write(
                self.style.SUCCESS(
                    "Demo recommendation backfill completed successfully."
                )
            )