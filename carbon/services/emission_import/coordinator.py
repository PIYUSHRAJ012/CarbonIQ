from pathlib import Path

from django.db import transaction

from carbon.services.emission_import.cea import CEASourceAdapter
from carbon.services.emission_import.importer import (
    EmissionFactorImporter,
)
from carbon.services.emission_import.retrieval import (
    CEASourceRetriever,
)
from carbon.services.emission_import.sources import (
    STATIC_SOURCE_ADAPTERS,
)
from carbon.services.emission_import.food import (
    IndiaFoodSourceAdapter,
)
from carbon.services.emission_import.fuel import (
    IndiaFuelSourceAdapter,
)
from carbon.services.emission_import.shopping import (
    IndiaShoppingSourceAdapter,
)
from carbon.services.emission_import.transport import (
    IndiaTransportSourceAdapter,
)
from carbon.services.emission_import.waste import (
    IndiaWasteSourceAdapter,
)

class EmissionFactorImportCoordinator:
    """
    Coordinates emission-factor imports from all configured sources.

    CEA:
        Retrieved dynamically from the official CEA website.

    Other sources:
        Provided through normalized source adapters.
    """

    @classmethod
    def import_latest_cea_factor(
        cls,
        destination_dir: str | Path | None = None,
    ) -> dict:
        """
        Import the latest CEA electricity emission factor.

        This method is retained for backwards compatibility and
        for dedicated CEA testing.
        """

        metadata, workbook_path = (
            CEASourceRetriever.download_latest(
                destination_dir=destination_dir,
            )
        )

        try:
            imported_factors = (
                CEASourceAdapter.get_factors_from_workbook(
                    workbook_path
                )
            )

            if not imported_factors:
                raise ValueError(
                    "CEA source returned no emission factors."
                )

            results = []

            for imported_factor in imported_factors:
                emission_factor, created = (
                    EmissionFactorImporter.import_factor(
                        imported_factor
                    )
                )

                results.append(
                    cls._build_result(
                        imported_factor,
                        emission_factor,
                        created,
                    )
                )

            return results[0]

        finally:
            workbook_path.unlink(missing_ok=True)

    @classmethod
    @transaction.atomic
    def import_all_factors(cls) -> dict:
        """
        Import emission factors from all configured sources.

        Returns:
            Summary containing per-source results.
        """

        summary = {
            "created": 0,
            "already_current": 0,
            "sources": [],
        }

        # ---------------------------------------------------------
        # 1. CEA
        # ---------------------------------------------------------

        cea_result = cls.import_latest_cea_factor()

        if cea_result["created"]:
            summary["created"] += 1
        else:
            summary["already_current"] += 1

        summary["sources"].append(
            cea_result
        )

        # ---------------------------------------------------------
        # 2. Static / versioned source adapters
        # ---------------------------------------------------------

        for adapter in STATIC_SOURCE_ADAPTERS:
            source_result = {
                "source": adapter.__name__,
                "created": 0,
                "already_current": 0,
                "factors": [],
            }

            factors = adapter.get_factors()

            for imported_factor in factors:
                emission_factor, created = (
                    EmissionFactorImporter.import_factor(
                        imported_factor
                    )
                )

                result = cls._build_result(
                    imported_factor,
                    emission_factor,
                    created,
                )

                source_result["factors"].append(
                    result
                )

                if created:
                    source_result["created"] += 1
                    summary["created"] += 1
                else:
                    source_result["already_current"] += 1
                    summary["already_current"] += 1

            summary["sources"].append(
                source_result
            )

        return summary

    @staticmethod
    def _build_result(
        imported_factor,
        emission_factor,
        created,
    ) -> dict:
        """
        Build a normalized result dictionary.
        """

        return {
            "source": imported_factor.source,
            "source_version": (
                imported_factor.source_version
            ),
            "category": (
                imported_factor.category_name
            ),
            "factor": imported_factor.factor,
            "unit": imported_factor.unit,
            "effective_from": (
                imported_factor.effective_from
            ),
            "effective_to": (
                imported_factor.effective_to
            ),
            "created": created,
            "emission_factor_id": (
                emission_factor.id
            ),
        }