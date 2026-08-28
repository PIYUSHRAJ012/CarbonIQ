from django.core.management.base import BaseCommand

from carbon.models import ActivityCategory, EmissionFactor

from carbon.seed_data.categories import DEFAULT_CATEGORIES
from carbon.seed_data.emission_factors import DEFAULT_EMISSION_FACTORS


class Command(BaseCommand):
    help = "Seed default activity categories and emission factors."

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.SUCCESS("Seeding Activity Categories...")
        )

        created_count = 0

        for category in DEFAULT_CATEGORIES:
            _, created = ActivityCategory.objects.get_or_create(
                name=category["name"],
                defaults=category,
            )

            if created:
                created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(f"✓ Created: {category['name']}")
                )
            else:
                self.stdout.write(
                    self.style.WARNING(f"- Already exists: {category['name']}")
                )

        self.stdout.write(
            self.style.SUCCESS("\nSeeding Emission Factors...")
        )

        factor_created_count = 0

        for factor_data in DEFAULT_EMISSION_FACTORS:
            category = ActivityCategory.objects.filter(
                name=factor_data["category"]
            ).first()

            if category is None:
                self.stdout.write(
                    self.style.ERROR(
                        f"Category '{factor_data['category']}' not found."
                    )
                )
                continue

            _, created = EmissionFactor.objects.get_or_create(
                activity_category=category,
                source=factor_data["source"],
                effective_from=factor_data["effective_from"],
                defaults={
                    "factor": factor_data["factor"],
                },
            )

            if created:
                factor_created_count += 1
                self.stdout.write(
                    self.style.SUCCESS(
                        f"✓ Created factor for {category.name}"
                    )
                )
            else:
                self.stdout.write(
                    self.style.WARNING(
                        f"- Factor already exists for {category.name}"
                    )
                )

        self.stdout.write(
            self.style.SUCCESS(
                "\n===================================="
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Categories created : {created_count}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                f"Emission factors created : {factor_created_count}"
            )
        )

        self.stdout.write(
            self.style.SUCCESS(
                "Database seeding completed successfully."
            )
        )
