from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal
from typing import Any


class OffsetSourceError(Exception):
    """
    Base exception for offset-source adapter failures.
    """


@dataclass(frozen=True)
class NormalizedOffsetProject:
    """
    Source-independent representation of an offset project.

    Source adapters convert registry-specific records into this
    normalized structure before CarbonIQ persists them.
    """

    name: str
    registry: str
    registry_project_id: str
    registry_url: str

    description: str = ""
    project_type: str = ""
    country: str = ""
    region: str = ""
    standard: str = ""
    status: str = "UNKNOWN"
    project_scale: str = ""

    annual_estimated_credits: Decimal | None = None

    sdg_impacts: tuple[dict[str, Any], ...] = ()

    project_developer: str = ""
    certification_documents_url: str = ""

    source_last_verified_at: datetime | None = None


class OffsetSourceAdapter:
    """
    Abstract contract for external offset registries.

    Concrete adapters must:
        1. retrieve source data,
        2. normalize the source representation,
        3. validate required fields,
        4. return NormalizedOffsetProject objects.

    Persistence belongs to the importer/service layer, not the
    source adapter itself.
    """

    registry_name: str = ""

    def fetch_projects(self) -> list[dict[str, Any]]:
        """
        Retrieve raw project records from the external source.
        """
        raise NotImplementedError

    def normalize_project(
        self,
        raw_project: dict[str, Any],
    ) -> NormalizedOffsetProject:
        """
        Convert one raw source record into CarbonIQ's normalized format.
        """
        raise NotImplementedError

    def fetch_and_normalize(self) -> list[NormalizedOffsetProject]:
        """
        Retrieve and normalize all available source projects.
        """
        raw_projects = self.fetch_projects()

        normalized_projects: list[NormalizedOffsetProject] = []

        for raw_project in raw_projects:
            try:
                normalized_projects.append(
                    self.normalize_project(raw_project)
                )
            except Exception as exc:
                raise OffsetSourceError(
                    "Failed to normalize an offset project "
                    f"from {self.registry_name}."
                ) from exc

        return normalized_projects