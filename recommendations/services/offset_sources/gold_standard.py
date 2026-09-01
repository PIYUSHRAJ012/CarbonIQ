from __future__ import annotations

from decimal import Decimal, InvalidOperation
from typing import Any

from django.utils import timezone

from .base import (
    NormalizedOffsetProject,
    OffsetSourceAdapter,
    OffsetSourceError,
)


class GoldStandardAdapter(OffsetSourceAdapter):
    """
    Adapter for the official Gold Standard Impact Registry CSV export.

    The current verified export contains:
        GSID
        Project Name
        Project Developer Name
        Status
        Sustainable Development Goals
        Project Type
        Country
        Description
        Estimated Annual Credits
        Methodology
        Size
        Programme of Activities
        POA GSID

    Only fields actually present in the export are mapped.
    """

    registry_name = "Gold Standard"

    REQUIRED_EXPORT_COLUMNS = {
        "GSID",
        "Project Name",
        "Project Developer Name",
        "Status",
        "Sustainable Development Goals",
        "Project Type",
        "Country",
        "Description",
        "Estimated Annual Credits",
        "Methodology",
        "Size",
        "Programme of Activities",
        "POA GSID",
    }

    STATUS_MAP = {
        "GOLD STANDARD CERTIFIED PROJECT": "ACTIVE",
        "GOLD STANDARD CERTIFIED DESIGN": "ACTIVE",
        "LISTED": "ACTIVE",
    }

    @staticmethod
    def _text(value: Any) -> str:
        """
        Normalize a source value into a clean string.
        """
        if value is None:
            return ""

        return str(value).strip()

    @staticmethod
    def _decimal(value: Any) -> Decimal | None:
        """
        Convert a numeric source value into Decimal safely.
        """
        if value is None:
            return None

        value_text = str(value).strip()

        if not value_text:
            return None

        value_text = value_text.replace(",", "")

        try:
            return Decimal(value_text)
        except InvalidOperation as exc:
            raise OffsetSourceError(
                f"Invalid Estimated Annual Credits value: {value!r}"
            ) from exc

    @staticmethod
    def _sdgs(value: Any) -> tuple[dict[str, Any], ...]:
        """
        Convert the Gold Standard SDG string:

            5,1,4,13,12

        into:

            (
                {"sdg": 5},
                {"sdg": 1},
                ...
            )
        """
        value_text = GoldStandardAdapter._text(value)

        if not value_text:
            return ()

        result: list[dict[str, Any]] = []

        for item in value_text.split(","):
            item = item.strip()

            if not item:
                continue

            try:
                sdg_number = int(item)
            except ValueError:
                raise OffsetSourceError(
                    f"Invalid SDG identifier: {item!r}"
                )

            if not 1 <= sdg_number <= 17:
                raise OffsetSourceError(
                    f"SDG identifier must be between 1 and 17: "
                    f"{sdg_number}"
                )

            result.append(
                {
                    "sdg": sdg_number,
                }
            )

        return tuple(result)

    @staticmethod
    def _status(value: Any) -> str:
        """
        Normalize verified Gold Standard export statuses.

        Unknown statuses are deliberately mapped to UNKNOWN rather
        than guessed.
        """
        status = (
            GoldStandardAdapter._text(value)
            .upper()
        )

        return GoldStandardAdapter.STATUS_MAP.get(
            status,
            "UNKNOWN",
        )

    @staticmethod
    def validate_export_columns(
        columns: list[str] | tuple[str, ...] | None,
    ) -> None:
        """
        Validate that the supplied CSV contains the complete verified
        Gold Standard export schema.
        """
        if not columns:
            raise OffsetSourceError(
                "Gold Standard CSV does not contain a header row."
            )

        normalized_columns = {
            str(column).strip()
            for column in columns
            if column is not None
        }

        missing_columns = (
            GoldStandardAdapter.REQUIRED_EXPORT_COLUMNS
            - normalized_columns
        )

        if missing_columns:
            missing_text = ", ".join(
                sorted(missing_columns)
            )

            raise OffsetSourceError(
                "Gold Standard export is missing required columns: "
                f"{missing_text}"
            )

    def fetch_projects(self) -> list[dict[str, Any]]:
        """
        Retrieval is handled by the management command.

        This adapter only normalizes records from the verified
        Gold Standard CSV export.
        """
        raise OffsetSourceError(
            "Gold Standard retrieval is file-based. "
            "Use the import_offset_projects management command."
        )

    def normalize_project(
        self,
        raw_project: dict[str, Any],
    ) -> NormalizedOffsetProject:
        """
        Normalize one record from the official Gold Standard CSV export.
        """

        if not isinstance(raw_project, dict):
            raise OffsetSourceError(
                "Gold Standard project record must be a dictionary."
            )

        gs_id = self._text(
            raw_project.get("GSID")
        )

        project_name = self._text(
            raw_project.get("Project Name")
        )

        developer = self._text(
            raw_project.get(
                "Project Developer Name"
            )
        )

        country = self._text(
            raw_project.get("Country")
        )

        if not gs_id:
            raise OffsetSourceError(
                "Gold Standard project is missing GSID."
            )

        if not project_name:
            raise OffsetSourceError(
                f"Gold Standard project {gs_id} "
                "is missing Project Name."
            )

        if not country:
            raise OffsetSourceError(
                f"Gold Standard project {gs_id} "
                "is missing Country."
            )

        registry_url = self._text(
            raw_project.get("registry_url")
        )

        if not registry_url:
            registry_url = (
                "https://registry.goldstandard.org/"
                f"projects/details/{gs_id}"
            )

        return NormalizedOffsetProject(
            name=project_name,
            registry=self.registry_name,
            registry_project_id=f"GS{gs_id}",
            registry_url=registry_url,

            description=self._text(
                raw_project.get("Description")
            ),

            project_type=self._text(
                raw_project.get("Project Type")
            ),

            country=country,

            # The verified CSV does not provide a separate region.
            region="",

            # The verified CSV provides Methodology but not a
            # standards-version field.
            standard="",

            status=self._status(
                raw_project.get("Status")
            ),

            project_scale=self._text(
                raw_project.get("Size")
            ),

            annual_estimated_credits=self._decimal(
                raw_project.get(
                    "Estimated Annual Credits"
                )
            ),

            sdg_impacts=self._sdgs(
                raw_project.get(
                    "Sustainable Development Goals"
                )
            ),

            project_developer=developer,

            # Certification-document URLs are not present in
            # the verified CSV export.
            certification_documents_url="",

            source_last_verified_at=timezone.now(),
        )