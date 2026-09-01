from django.core.management.base import BaseCommand, CommandError

from carbon.services.benchmark_import.coordinator import (
    CarbonBenchmarkImportCoordinator,
)


class Command(BaseCommand):
    """
    Import the validated India carbon-footprint benchmark dataset.
    """

    help = (
        "Import validated India carbon-footprint "
        "benchmark data."
    )

    def handle(self, *args, **options):

        self.stdout.write(
            self.style.NOTICE(
                "Importing India carbon-footprint benchmarks..."
            )
        )

        try:
            result = (
                CarbonBenchmarkImportCoordinator
                .import_all()
            )

        except Exception as exc:
            raise CommandError(
                f"Benchmark import failed: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "\nBenchmark import completed."
            )
        )

        self.stdout.write(
            f"District records created       : "
            f"{result['district_created']}"
        )

        self.stdout.write(
            f"District records already exist : "
            f"{result['district_already_current']}"
        )

        self.stdout.write(
            f"National record created        : "
            f"{result['national_created']}"
        )

        self.stdout.write(
            f"National record already exists : "
            f"{result['national_already_current']}"
        )

        self.stdout.write(
            f"Total records                  : "
            f"{result['total_records']}"
        )

        self.stdout.write(
            f"Total created                  : "
            f"{result['total_created']}"
        )

        self.stdout.write(
            f"Total already current          : "
            f"{result['total_already_current']}"
        )