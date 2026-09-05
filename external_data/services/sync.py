from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Iterable

from django.db import transaction
from django.utils import timezone

from external_data.models import ExternalEnvironmentalObservation
from external_data.providers.india_energy_atlas import (
    IndiaEnergyAtlasProvider,
)


@dataclass(frozen=True)
class SyncResult:
    """
    Summary of a single external-data synchronization run.
    """

    fetched: int = 0
    created: int = 0
    updated: int = 0
    skipped: int = 0


class ExternalDataSyncService:
    """
    Coordinates fetching external environmental observations and
    persisting them into CarbonIQ's normalized observation model.
    """

    def __init__(self, provider=None):
        self.provider = provider or IndiaEnergyAtlasProvider()

    @transaction.atomic
    def sync_grid_carbon_intensity(
        self,
        *,
        states: Iterable[str] | None = None,
    ) -> SyncResult:
        """
        Fetch state-level grid carbon-intensity observations and persist them.

        The operation is idempotent: the same provider observation can be
        synchronized repeatedly without creating duplicate rows.
        """

        observations = self.provider.fetch_carbon_intensity(
            states=states,
        )

        result = SyncResult()

        for observation in observations:
            normalized = self._normalize_observation(observation)

            if normalized is None:
                result = SyncResult(
                    fetched=result.fetched + 1,
                    created=result.created,
                    updated=result.updated,
                    skipped=result.skipped + 1,
                )
                continue

            created = self._persist_observation(normalized)

            result = SyncResult(
                fetched=result.fetched + 1,
                created=result.created + int(created),
                updated=result.updated + int(not created),
                skipped=result.skipped,
            )

        return result

    @staticmethod
    def _normalize_observation(observation: dict) -> dict | None:
        """
        Validate and normalize a provider observation before persistence.
        """

        timestamp = observation.get("timestamp")
        state = observation.get("state")
        carbon_intensity = observation.get("carbon_intensity_gco2_kwh")

        if not timestamp or not state or carbon_intensity is None:
            return None

        try:
            carbon_intensity = Decimal(str(carbon_intensity))
        except (InvalidOperation, TypeError, ValueError):
            return None

        if carbon_intensity < 0:
            return None

        observed_at = timestamp

        if timezone.is_naive(observed_at):
            observed_at = timezone.make_aware(
                observed_at,
                timezone.get_current_timezone(),
            )

        source = observation.get("source", "unknown")

        return {
            "provider": "india_energy_atlas",
            "data_type": "GRID_CARBON_INTENSITY",
            "zone": str(observation["state"]).strip().lower(),
            "value": carbon_intensity,
            "unit": "gCO2e/kWh",
            "observed_at": observed_at,
            "provider_updated_at": None,
            "fetched_at": timezone.now(),
            "is_estimated": source == "estimated_from_prior_day",
            "estimation_method": source or "provider_reported",
            "temporal_granularity": "hourly",
            "emission_factor_type": "lifecycle",
            "flow_traced": False,
            "source_url": (
                "https://www.energymap.in/developer/"
            ),
        }

    @staticmethod
    def _persist_observation(data: dict) -> bool:
        """
        Persist one normalized observation.

        Returns:
            True  -> row created
            False -> existing row updated
        """

        lookup = {
            "provider": data["provider"],
            "data_type": data["data_type"],
            "zone": data["zone"],
            "observed_at": data["observed_at"],
            "temporal_granularity": data["temporal_granularity"],
            "emission_factor_type": data["emission_factor_type"],
            "flow_traced": data["flow_traced"],
        }

        defaults = {
            "value": data["value"],
            "unit": data["unit"],
            "provider_updated_at": data["provider_updated_at"],
            "fetched_at": data["fetched_at"],
            "is_estimated": data["is_estimated"],
            "estimation_method": data["estimation_method"],
            "source_url": data["source_url"],
        }

        _, created = ExternalEnvironmentalObservation.objects.update_or_create(
            **lookup,
            defaults=defaults,
        )

        return created