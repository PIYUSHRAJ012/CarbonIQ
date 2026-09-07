from django.core.management.base import BaseCommand

from accounts.models import CustomUser
from gamification.services.achievements import evaluate_achievements


class Command(BaseCommand):
    help = "Backfill eligible achievements for all existing users."

    def handle(self, *args, **options):
        self.stdout.write("Backfilling sustainability achievements...")

        users_processed = 0
        achievements_awarded = 0

        users = CustomUser.objects.all().order_by("id")

        for user in users:
            result = evaluate_achievements(user)

            users_processed += 1
            achievements_awarded += len(result.newly_awarded)

            if result.newly_awarded:
                names = ", ".join(
                    achievement.name
                    for achievement in result.newly_awarded
                )

                self.stdout.write(
                    f"✓ {user.email}: {names}"
                )

        self.stdout.write("")
        self.stdout.write(
            f"Users processed      : {users_processed}"
        )
        self.stdout.write(
            f"Achievements awarded : {achievements_awarded}"
        )
        self.stdout.write(
            "Achievement backfill completed successfully."
        )