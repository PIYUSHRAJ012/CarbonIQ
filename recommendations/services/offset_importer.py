from __future__ import annotations

from dataclasses import dataclass
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from recommendations.models import OffsetProject
from recommendations.services.offset_sources.base import (
    NormalizedOffsetProject,
    OffsetSourceError,
)


class OffsetImportError(Exception):
    """
    Raised when an offset-project import cannot be completed safely.
    """


@dataclass(frozen=True)
class OffsetImportResult:
    """
    Statistics describing one offset-project import operation.
    """

    created: int
    updated: int
    unchanged: int


class OffsetProjectImportService:
    """
    Persist normalized external offset-project records into the
    CarbonIQ local PostgreSQL catalog.

    The service is deliberately independent of any specific registry.
    Source adapters are responsible for converting external records
    into NormalizedOffsetProject objects.
    """

    @staticmethod
    def _validate_project(
        project: NormalizedOffsetProject,
    ) -> None:
        """
        Validate fields that are required before persistence.
        """

        required_fields = {
            "name": project.name,
            "registry": project.registry,
            "registry_project_id": project.registry_project_id,
            "registry_url": project.registry_url,
        }

        missing_fields = [
            field_name
            for field_name, value in required_fields.items()
            if not str(value).strip()
        ]

        if missing_fields:
            raise OffsetImportError(
                "Offset project is missing required fields: "
                + ", ".join(missing_fields)
            )

        if project.annual_estimated_credits is not None:
            if project.annual_estimated_credits < 0:
                raise OffsetImportError(
                    "Annual estimated credits cannot be negative."
                )

    @staticmethod
    def _build_defaults(
        project: NormalizedOffsetProject,
    ) -> dict:
        """
        Convert the normalized project into OffsetProject model fields.
        """

        return {
            "name": project.name,
            "description": project.description,
            "project_type": project.project_type,
            "country": project.country,
            "region": project.region,
            "registry_url": project.registry_url,
            "standard": project.standard,
            "status": project.status,
            "project_scale": project.project_scale,
            "annual_estimated_credits": (
                project.annual_estimated_credits
            ),
            "sdg_impacts": list(project.sdg_impacts),
            "project_developer": project.project_developer,
            "certification_documents_url": (
                project.certification_documents_url
            ),
            "source_last_verified_at": (
                project.source_last_verified_at
                or timezone.now()
            ),
            "is_active": True,
        }

    @classmethod
    def import_projects(
        cls,
        projects: Iterable[NormalizedOffsetProject],
    ) -> OffsetImportResult:
        """
        Import normalized offset projects atomically.

        Projects are identified by the external registry and registry
        project ID.

        Metadata changes are counted as updates. A verification timestamp
        is refreshed on every successful verification but does not cause
        a project to be counted as updated.
        """

        project_list = list(projects)

        created = 0
        updated = 0
        unchanged = 0

        try:
            with transaction.atomic():
                for project in project_list:
                    cls._validate_project(project)

                    defaults = cls._build_defaults(project)

                    existing = (
                        OffsetProject.objects.filter(
                            registry=project.registry,
                            registry_project_id=(
                                project.registry_project_id
                            ),
                        )
                        .first()
                    )

                    if existing is None:
                        OffsetProject.objects.create(
                            registry=project.registry,
                            registry_project_id=(
                                project.registry_project_id
                            ),
                            **defaults,
                        )

                        created += 1
                        continue

                    metadata_fields = {
                        field_name: value
                        for field_name, value in defaults.items()
                        if field_name != "source_last_verified_at"
                    }

                    metadata_changed = any(
                        getattr(existing, field_name) != value
                        for field_name, value in metadata_fields.items()
                    )

                    if metadata_changed:
                        for field_name, value in defaults.items():
                            setattr(
                                existing,
                                field_name,
                                value,
                            )

                        existing.save()

                        updated += 1
                        continue

                    # Metadata is unchanged. The project was still
                    # successfully verified against the source, so refresh
                    # the verification timestamp without counting an update.
                    existing.source_last_verified_at = (
                        defaults["source_last_verified_at"]
                    )

                    existing.save(
                        update_fields=[
                            "source_last_verified_at",
                            "updated_at",
                        ]
                    )

                    unchanged += 1

        except OffsetImportError:
            raise

        except Exception as exc:
            raise OffsetImportError(
                "Offset-project import failed. "
                "All database changes were rolled back."
            ) from exc

        return OffsetImportResult(
            created=created,
            updated=updated,
            unchanged=unchanged,
        )