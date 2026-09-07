from datetime import timedelta

from django.core.management.base import BaseCommand
from django.utils import timezone

from gamification.models import Challenge


class Command(BaseCommand):
    help = "Seed default CarbonIQ sustainability challenges."

    def handle(self, *args, **options):
        today = timezone.localdate()
        end_date = today + timedelta(days=90)

        challenges = [
            {
                "code": "REDUCE_EMISSIONS_10",
                "title": "Reduce Your Emissions by 10%",
                "description": (
                    "Reduce your latest monthly carbon footprint by at least "
                    "10% compared with the previous completed month."
                ),
                "metric": Challenge.Metric.EMISSION_REDUCTION,
                "target": 10,
                "start_date": today,
                "end_date": end_date,
            },
            {
                "code": "COMPLETE_3_ACTIONS",
                "title": "Complete 3 Sustainability Actions",
                "description": (
                    "Complete three personalized sustainability recommendations "
                    "to strengthen your sustainable habits."
                ),
                "metric": Challenge.Metric.SUSTAINABLE_ACTIONS,
                "target": 3,
                "start_date": today,
                "end_date": end_date,
            },
            {
                "code": "IMPROVE_2_MONTHS",
                "title": "Improve for 2 Months",
                "description": (
                    "Achieve a lower carbon footprint than the previous month "
                    "for two month-to-month transitions."
                ),
                "metric": Challenge.Metric.MONTHLY_IMPROVEMENT,
                "target": 2,
                "start_date": today,
                "end_date": end_date,
            },
            {
                "code": "LOW_EMISSION_MONTH",
                "title": "Beat Your Benchmark",
                "description": (
                    "Record one completed month at or below your resolved "
                    "CarbonIQ monthly benchmark."
                ),
                "metric": Challenge.Metric.LOW_EMISSION_PERIOD,
                "target": 1,
                "start_date": today,
                "end_date": end_date,
            },
        ]

        created_count = 0
        existing_count = 0

        self.stdout.write("Seeding sustainability challenges...")

        for challenge_data in challenges:
            challenge, created = Challenge.objects.get_or_create(
                code=challenge_data["code"],
                defaults={
                    "title": challenge_data["title"],
                    "description": challenge_data["description"],
                    "metric": challenge_data["metric"],
                    "target": challenge_data["target"],
                    "start_date": challenge_data["start_date"],
                    "end_date": challenge_data["end_date"],
                    "is_active": True,
                },
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created: {challenge.title}"
                    )
                )
            else:
                existing_count += 1
                self.stdout.write(
                    f"• Already exists: {challenge.title}"
                )

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                f"Challenges created : {created_count}"
            )
        )
        self.stdout.write(
            f"Challenges existing: {existing_count}"
        )
        self.stdout.write(
            self.style.SUCCESS(
                "Challenge seeding completed successfully."
            )
        )