from django.core.management.base import BaseCommand

from gamification.models import Achievement


class Command(BaseCommand):
    help = "Seed default CarbonIQ sustainability achievements."

    def handle(self, *args, **options):
        achievements = [
            {
                "code": "FIRST_FOOTPRINT",
                "name": "First Footprint",
                "description": (
                    "Record your first completed carbon footprint."
                ),
                "icon": "bi-footprints",
            },
            {
                "code": "CONSISTENT_TRACKER",
                "name": "Consistent Tracker",
                "description": (
                    "Track your carbon footprint across at least "
                    "3 completed months."
                ),
                "icon": "bi-calendar-check",
            },
            {
                "code": "EMISSION_REDUCER",
                "name": "Emission Reducer",
                "description": (
                    "Reduce your latest monthly emissions by at least "
                    "10% compared with the previous completed month."
                ),
                "icon": "bi-graph-down-arrow",
            },
            {
                "code": "SUSTAINABILITY_ACTION_CHAMPION",
                "name": "Sustainability Action Champion",
                "description": (
                    "Complete at least 3 personalized sustainability "
                    "recommendations."
                ),
                "icon": "bi-stars",
            },
            {
                "code": "LOW_CARBON_MONTH",
                "name": "Low Carbon Month",
                "description": (
                    "Record a completed month at or below your "
                    "resolved CarbonIQ benchmark."
                ),
                "icon": "bi-leaf",
            },
        ]

        created_count = 0
        existing_count = 0

        self.stdout.write("Seeding sustainability achievements...")

        for achievement_data in achievements:
            achievement, created = Achievement.objects.get_or_create(
                code=achievement_data["code"],
                defaults={
                    "name": achievement_data["name"],
                    "description": achievement_data["description"],
                    "icon": achievement_data["icon"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created: {achievement.name}"
                    )
                )
            else:
                existing_count += 1
                self.stdout.write(
                    f"• Already exists: {achievement.name}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Achievements created : {created_count}"
            )
        )
        self.stdout.write(
            f"Achievements existing: {existing_count}"
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Achievement seeding completed successfully."
            )
        )