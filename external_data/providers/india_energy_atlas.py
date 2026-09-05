from __future__ import annotations

from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any

import requests
from django.conf import settings


class IndiaEnergyAtlasProviderError(Exception):
    """Raised when India Energy Atlas data cannot be fetched or validated."""


class IndiaEnergyAtlasProvider:
    """
    Provider adapter for India Energy Atlas developer API.

    This class is responsible only for communicating with the external API
    and normalizing its response. Database persistence belongs to the sync
    service.
    """

    PROVIDER_NAME = "india_energy_atlas"
    CARBON_INTENSITY_ENDPOINT = "/carbon-intensity/by-state"

    def __init__(self) -> None:
        self.api_key = getattr(settings, "INDIA_ENERGY_ATLAS_API_KEY", None)
        self.base_url = getattr(
            settings,
            "INDIA_ENERGY_ATLAS_API_BASE_URL",
            "https://api.energymap.in/developer/v1",
        )

        if not self.api_key:
            raise IndiaEnergyAtlasProviderError(
                "INDIA_ENERGY_ATLAS_API_KEY is not configured."
            )

    def fetch_carbon_intensity(
        self,
        *,
        states: list[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Fetch state-level grid carbon-intensity observations.

        Args:
            states: Optional list of state names/slugs. When omitted, the
                    provider response is returned for all available states.

        Returns:
            A list of normalized observation dictionaries.
        """

        url = f"{self.base_url.rstrip('/')}{self.CARBON_INTENSITY_ENDPOINT}"

        params: dict[str, Any] = {}

        if states:
            params["states"] = ",".join(states)

        try:
            response = requests.get(
                url,
                headers={
                    "X-API-Key": self.api_key,
                    "Accept": "application/json",
                },
                params=params,
                timeout=20,
            )
        except requests.RequestException as exc:
            raise IndiaEnergyAtlasProviderError(
                f"India Energy Atlas request failed: {exc}"
            ) from exc

        if response.status_code == 401:
            raise IndiaEnergyAtlasProviderError(
                "India Energy Atlas authentication failed."
            )

        if response.status_code == 403:
            raise IndiaEnergyAtlasProviderError(
                "India Energy Atlas access denied for the configured API tier."
            )

        if response.status_code >= 400:
            raise IndiaEnergyAtlasProviderError(
                f"India Energy Atlas returned HTTP {response.status_code}: "
                f"{response.text[:500]}"
            )

        try:
            payload = response.json()
        except ValueError as exc:
            raise IndiaEnergyAtlasProviderError(
                "India Energy Atlas returned invalid JSON."
            ) from exc

        raw_observations = self._extract_observations(payload)

        normalized: list[dict[str, Any]] = []

        for item in raw_observations:
            observation = self._normalize_observation(item)

            if observation is not None:
                normalized.append(observation)

        if states:
            requested_states = {
                state.strip().lower()
                for state in states
                if state and state.strip()
            }

            normalized = [
                observation
                for observation in normalized
                if observation["state_slug"] in requested_states
            ]

        return normalized

    @staticmethod
    def _extract_observations(payload: Any) -> list[dict[str, Any]]:
        """
        Extract the observation list from the provider response.
        """

        if isinstance(payload, list):
            return [
                item
                for item in payload
                if isinstance(item, dict)
            ]

        if not isinstance(payload, dict):
            raise IndiaEnergyAtlasProviderError(
                "India Energy Atlas response has an unexpected structure."
            )

        data = payload.get("data")

        if isinstance(data, list):
            return [
                item
                for item in data
                if isinstance(item, dict)
            ]

        if isinstance(data, dict):
            for key in ("observations", "results", "items"):
                value = data.get(key)

                if isinstance(value, list):
                    return [
                        item
                        for item in value
                        if isinstance(item, dict)
                    ]

        for key in ("observations", "results", "items"):
            value = payload.get(key)

            if isinstance(value, list):
                return [
                    item
                    for item in value
                    if isinstance(item, dict)
                ]

        raise IndiaEnergyAtlasProviderError(
            "India Energy Atlas response does not contain observations."
        )

    @staticmethod
    def _normalize_observation(
        item: dict[str, Any],
    ) -> dict[str, Any] | None:
        """
        Normalize one raw provider observation.

        Invalid observations are skipped rather than persisted.
        """

        timestamp = item.get("timestamp")
        state = item.get("state")
        intensity = item.get("carbon_intensity_gco2_kwh")

        if not timestamp or not state or intensity is None:
            return None

        try:
            carbon_intensity = Decimal(str(intensity))
        except (InvalidOperation, TypeError, ValueError):
            return None

        if carbon_intensity < 0:
            return None

        parsed_timestamp = IndiaEnergyAtlasProvider._parse_timestamp(
            timestamp
        )

        if parsed_timestamp is None:
            return None

        source = item.get("source")

        return {
            "timestamp": parsed_timestamp,
            "state": str(state).strip(),
            "state_slug": str(
                item.get("state_slug") or state
            ).strip().lower(),
            "carbon_intensity_gco2_kwh": carbon_intensity,
            "intensity_class": item.get("intensity_class"),
            "total_generation_mw": item.get("total_generation_mw"),
            "dominant_fuel": item.get("dominant_fuel"),
            "source": source,
            "confidence": item.get("confidence"),
            "emission_factors_version": item.get(
                "emission_factors_version"
            ),
            "scope_key": item.get("scope_key"),
            "emission_factors_basis": item.get(
                "emission_factors_basis"
            ),
        }

    @staticmethod
    def _parse_timestamp(value: Any) -> datetime | None:
        """
        Parse ISO-8601 timestamps returned by the provider.
        """

        if not isinstance(value, str):
            return None

        try:
            return datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError:
            return None