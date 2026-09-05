from django.core.management.base import BaseCommand, CommandError

from external_data.services.sync import (
    ExternalDataSyncService,
)


class Command(BaseCommand):
    help = "Synchronize external environmental observations into CarbonIQ."

    def add_arguments(self, parser):
        parser.add_argument(
            "--state",
            action="append",
            dest="states",
            help=(
                "State slug to synchronize. "
                "Can be supplied multiple times. "
                "Example: --state karnataka --state maharashtra"
            ),
        )

    def handle(self, *args, **options):
        states = options.get("states")

        self.stdout.write(
            self.style.NOTICE(
                "Starting CarbonIQ external-data synchronization..."
            )
        )

        try:
            result = (
                ExternalDataSyncService()
                .sync_grid_carbon_intensity(states=states)
            )
        except Exception as exc:
            raise CommandError(
                f"External-data synchronization failed: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "External-data synchronization completed."
            )
        )

        self.stdout.write(f"Fetched : {result.fetched}")
        self.stdout.write(f"Created : {result.created}")
        self.stdout.write(f"Updated : {result.updated}")
        self.stdout.write(f"Skipped : {result.skipped}")