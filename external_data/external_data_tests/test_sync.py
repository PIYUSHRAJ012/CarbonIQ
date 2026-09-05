from datetime import datetime, timezone
from decimal import Decimal

from django.test import TestCase

from external_data.models import ExternalEnvironmentalObservation
from external_data.services.sync import (
    ExternalDataSyncService,
)


class MockIndiaEnergyAtlasProvider:
    """Deterministic provider used for sync-service unit tests."""

    def __init__(self, observations=None):
        self.observations = observations or []

    def fetch_carbon_intensity(self, *, states=None):
        observations = self.observations

        if states:
            requested_states = {
                state.strip().lower()
                for state in states
            }

            observations = [
                observation
                for observation in observations
                if observation["state_slug"] in requested_states
            ]

        return observations


class ExternalDataSyncServiceTests(TestCase):
    def setUp(self):
        self.timestamp = datetime(
            2026,
            9,
            5,
            9,
            0,
            tzinfo=timezone.utc,
        )

        self.observations = [
            {
                "timestamp": self.timestamp,
                "state": "karnataka",
                "state_slug": "karnataka",
                "carbon_intensity_gco2_kwh": Decimal("335.32"),
                "intensity_class": "green",
                "total_generation_mw": 14739.336,
                "dominant_fuel": "solar",
                "source": "estimated_from_prior_day",
                "confidence": 0.4,
                "emission_factors_version": "cea_co2_baseline_v18",
                "scope_key": "karnataka",
                "emission_factors_basis": "lifecycle",
            },
            {
                "timestamp": datetime(
                    2026,
                    9,
                    5,
                    8,
                    0,
                    tzinfo=timezone.utc,
                ),
                "state": "maharashtra",
                "state_slug": "maharashtra",
                "carbon_intensity_gco2_kwh": Decimal("421.75"),
                "intensity_class": "yellow",
                "total_generation_mw": 12000.0,
                "dominant_fuel": "coal",
                "source": "derived_aggregate",
                "confidence": 0.6,
                "emission_factors_version": "cea_co2_baseline_v18",
                "scope_key": "maharashtra",
                "emission_factors_basis": "lifecycle",
            },
        ]

    def test_sync_creates_observations(self):
        provider = MockIndiaEnergyAtlasProvider(self.observations)
        service = ExternalDataSyncService(provider=provider)

        result = service.sync_grid_carbon_intensity()

        self.assertEqual(result.fetched, 2)
        self.assertEqual(result.created, 2)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 0)

        self.assertEqual(
            ExternalEnvironmentalObservation.objects.count(),
            2,
        )

    def test_sync_is_idempotent(self):
        provider = MockIndiaEnergyAtlasProvider(self.observations)
        service = ExternalDataSyncService(provider=provider)

        first_result = service.sync_grid_carbon_intensity()
        second_result = service.sync_grid_carbon_intensity()

        self.assertEqual(first_result.created, 2)
        self.assertEqual(first_result.updated, 0)

        self.assertEqual(second_result.created, 0)
        self.assertEqual(second_result.updated, 2)

        self.assertEqual(
            ExternalEnvironmentalObservation.objects.count(),
            2,
        )

    def test_state_filtering(self):
        provider = MockIndiaEnergyAtlasProvider(self.observations)
        service = ExternalDataSyncService(provider=provider)

        result = service.sync_grid_carbon_intensity(
            states=["karnataka"],
        )

        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.created, 1)

        self.assertEqual(
            ExternalEnvironmentalObservation.objects.count(),
            1,
        )

        observation = (
            ExternalEnvironmentalObservation.objects.first()
        )

        self.assertEqual(observation.zone, "karnataka")

    def test_invalid_observation_is_skipped(self):
        invalid_observation = {
            "timestamp": self.timestamp,
            "state": "karnataka",
            "state_slug": "karnataka",
            "carbon_intensity_gco2_kwh": "-10",
        }

        provider = MockIndiaEnergyAtlasProvider(
            [invalid_observation]
        )
        service = ExternalDataSyncService(provider=provider)

        result = service.sync_grid_carbon_intensity()

        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 1)

        self.assertEqual(
            ExternalEnvironmentalObservation.objects.count(),
            0,
        )

    def test_missing_required_fields_are_skipped(self):
        invalid_observation = {
            "timestamp": self.timestamp,
            "state": "karnataka",
        }

        provider = MockIndiaEnergyAtlasProvider(
            [invalid_observation]
        )
        service = ExternalDataSyncService(provider=provider)

        result = service.sync_grid_carbon_intensity()

        self.assertEqual(result.fetched, 1)
        self.assertEqual(result.created, 0)
        self.assertEqual(result.updated, 0)
        self.assertEqual(result.skipped, 1)

        self.assertEqual(
            ExternalEnvironmentalObservation.objects.count(),
            0,
        )

    def test_estimated_observation_is_preserved(self):
        provider = MockIndiaEnergyAtlasProvider(
            [self.observations[0]]
        )
        service = ExternalDataSyncService(provider=provider)

        service.sync_grid_carbon_intensity()

        observation = (
            ExternalEnvironmentalObservation.objects.get()
        )

        self.assertTrue(observation.is_estimated)
        self.assertEqual(
            observation.estimation_method,
            "estimated_from_prior_day",
        )

    def test_lifecycle_and_hourly_values_are_stored(self):
        provider = MockIndiaEnergyAtlasProvider(
            [self.observations[0]]
        )
        service = ExternalDataSyncService(provider=provider)

        service.sync_grid_carbon_intensity()

        observation = (
            ExternalEnvironmentalObservation.objects.get()
        )

        self.assertEqual(
            observation.temporal_granularity,
            "hourly",
        )
        self.assertEqual(
            observation.emission_factor_type,
            "lifecycle",
        )
        self.assertEqual(
            observation.provider,
            "india_energy_atlas",
        )