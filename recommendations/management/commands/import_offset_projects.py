from __future__ import annotations

import csv
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from recommendations.services.offset_importer import (
    OffsetImportError,
    OffsetProjectImportService,
)
from recommendations.services.offset_sources.base import (
    OffsetSourceError,
)
from recommendations.services.offset_sources.gold_standard import (
    GoldStandardAdapter,
)


class Command(BaseCommand):
    help = (
        "Import Gold Standard offset projects from the official "
        "Impact Registry CSV export."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "csv_file",
            type=str,
            help=(
                "Path to the official Gold Standard "
                "Impact Registry CSV export."
            ),
        )

        parser.add_argument(
            "--dry-run",
            action="store_true",
            help=(
                "Validate and normalize the CSV without "
                "writing projects to the database."
            ),
        )

    def handle(self, *args, **options):
        csv_path = Path(
            options["csv_file"]
        ).expanduser()

        if not csv_path.exists():
            raise CommandError(
                f"CSV file does not exist: {csv_path}"
            )

        if not csv_path.is_file():
            raise CommandError(
                f"CSV path is not a file: {csv_path}"
            )

        if csv_path.suffix.lower() != ".csv":
            raise CommandError(
                "The supplied file must have a .csv extension."
            )

        try:
            raw_projects = self._read_csv(
                csv_path
            )

            adapter = GoldStandardAdapter()

            normalized_projects = [
                adapter.normalize_project(
                    record
                )
                for record in raw_projects
            ]

            if options["dry_run"]:
                self.stdout.write("")
                self.stdout.write(
                    self.style.SUCCESS(
                        "Gold Standard CSV dry-run completed successfully."
                    )
                )

                self.stdout.write("=" * 55)

                self.stdout.write(
                    f"Source file        : {csv_path}"
                )

                self.stdout.write(
                    f"Projects validated : {len(normalized_projects)}"
                )

                self.stdout.write(
                    "Database changes   : 0"
                )

                self.stdout.write(
                    "Validated at       : "
                    f"{timezone.now():%Y-%m-%d %H:%M:%S %Z}"
                )

                return

            result = (
                OffsetProjectImportService.import_projects(
                    normalized_projects
                )
            )

        except (
            OffsetImportError,
            OffsetSourceError,
            OSError,
            csv.Error,
        ) as exc:
            raise CommandError(
                f"Offset-project import failed: {exc}"
            ) from exc

        self.stdout.write("")
        self.stdout.write(
            self.style.SUCCESS(
                "CarbonIQ Gold Standard Offset Project Import"
            )
        )

        self.stdout.write("=" * 55)

        self.stdout.write(
            f"Source file        : {csv_path}"
        )

        self.stdout.write(
            f"Projects read      : {len(raw_projects)}"
        )

        self.stdout.write(
            f"Projects created   : {result.created}"
        )

        self.stdout.write(
            f"Projects updated   : {result.updated}"
        )

        self.stdout.write(
            f"Projects unchanged : {result.unchanged}"
        )

        self.stdout.write(
            "Imported at        : "
            f"{timezone.now():%Y-%m-%d %H:%M:%S %Z}"
        )

    @staticmethod
    def _read_csv(
        csv_path: Path,
    ) -> list[dict]:
        """
        Read and validate the official Gold Standard
        Impact Registry CSV export.
        """

        try:
            with csv_path.open(
                mode="r",
                encoding="utf-8-sig",
                newline="",
            ) as csv_file:
                reader = csv.DictReader(
                    csv_file
                )

                GoldStandardAdapter.validate_export_columns(
                    reader.fieldnames
                )

                rows: list[dict] = []

                for row in reader:
                    cleaned_row = {
                        str(key).strip(): value
                        for key, value in row.items()
                        if key is not None
                    }

                    rows.append(
                        cleaned_row
                    )

                return rows

        except UnicodeDecodeError as exc:
            raise csv.Error(
                "CSV file is not valid UTF-8 text."
            ) from exc