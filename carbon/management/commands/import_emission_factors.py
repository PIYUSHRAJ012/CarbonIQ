from django.core.management.base import BaseCommand, CommandError

from carbon.services.emission_import.coordinator import (
    EmissionFactorImportCoordinator,
)


class Command(BaseCommand):
    """
    Import the latest authoritative emission factors.
    """

    help = (
        "Retrieve and import the latest available "
        "authoritative emission factors."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Checking for updated emission factors..."
            )
        )

        try:
            result = (
                EmissionFactorImportCoordinator
                .import_all_factors()
            )
        except Exception as exc:
            raise CommandError(
                f"Emission-factor import failed: {exc}"
            ) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "\nEmission-factor import completed."
            )
        )

        self.stdout.write(
            f"Factors created        : {result['created']}"
        )

        self.stdout.write(
            f"Factors already current: "
            f"{result['already_current']}"
        )

        for source in result["sources"]:
            # CEA returns a single-factor result while the
            # other adapters return grouped factor results.
            if "factors" in source:
                self.stdout.write(
                    f"\nSource: {source['source']}"
                )

                self.stdout.write(
                    f"Created: {source['created']}"
                )

                self.stdout.write(
                    f"Already current: "
                    f"{source['already_current']}"
                )

                for factor in source["factors"]:
                    unit = factor["unit"].replace("₹", "INR")

                    self.stdout.write(
                        "  - "
                        f"{factor['category']} | "
                        f"{factor['factor']} "
                        f"{unit} | "
                        f"{factor['source_version']}"
                    )
            else:
                status = (
                    "created"
                    if source["created"]
                    else "already current"
                )

                self.stdout.write(
                    f"\nSource: {source['source']}"
                )

                self.stdout.write(
                    f"  {source['category']} | "
                    f"{source['factor']} "
                    f"{source['unit']} | "
                    f"{source['source_version']} | "
                    f"{status}"
                )