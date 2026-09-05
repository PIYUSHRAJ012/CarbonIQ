from django.db import models

from core.models import TimeStampedModel


class ExternalEnvironmentalObservation(TimeStampedModel):
    """
    Stores a time-stamped observation retrieved from an
    external environmental data provider.
    """

    class DataType(models.TextChoices):
        GRID_CARBON_INTENSITY = "GRID_CARBON_INTENSITY", "Grid Carbon Intensity"

    class TemporalGranularity(models.TextChoices):
        FIVE_MINUTES = "5_minutes", "5 Minutes"
        FIFTEEN_MINUTES = "15_minutes", "15 Minutes"
        HOURLY = "hourly", "Hourly"

    class EmissionFactorType(models.TextChoices):
        LIFECYCLE = "lifecycle", "Lifecycle"
        DIRECT = "direct", "Direct"

    provider = models.CharField(
        max_length=100,
        help_text="Name of the external data provider.",
    )

    data_type = models.CharField(
        max_length=50,
        choices=DataType.choices,
        help_text="Type of environmental observation.",
    )

    zone = models.CharField(
        max_length=50,
        help_text="External provider zone identifier.",
    )

    value = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        help_text="Observed environmental value.",
    )

    unit = models.CharField(
        max_length=50,
        help_text="Unit of the observed value.",
    )

    observed_at = models.DateTimeField(
        help_text="Timestamp represented by the observation.",
    )

    provider_updated_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Timestamp at which the provider last updated the observation.",
    )

    fetched_at = models.DateTimeField(
        help_text="Timestamp when CarbonIQ retrieved the observation.",
    )

    is_estimated = models.BooleanField(
        default=False,
        help_text="Whether the provider marked this observation as estimated.",
    )

    estimation_method = models.CharField(
        max_length=100,
        blank=True,
        default="",
        help_text="Estimation method reported by the provider, if available.",
    )

    temporal_granularity = models.CharField(
        max_length=20,
        choices=TemporalGranularity.choices,
        default=TemporalGranularity.HOURLY,
        help_text="Temporal resolution of the observation.",
    )

    emission_factor_type = models.CharField(
        max_length=20,
        choices=EmissionFactorType.choices,
        default=EmissionFactorType.LIFECYCLE,
        help_text="Emission factor methodology used by the provider.",
    )

    flow_traced = models.BooleanField(
        default=False,
        help_text="Whether flow-traced electricity data was used.",
    )

    source_url = models.URLField(
        max_length=500,
        help_text="Source URL for traceability.",
    )

    class Meta:
        ordering = ("-observed_at", "-fetched_at")
        indexes = [
            models.Index(
                fields=("provider", "data_type", "zone", "observed_at"),
                name="ext_obs_provider_data_idx",
            ),
            models.Index(
                fields=("zone", "observed_at"),
                name="ext_obs_zone_observed_idx",
            ),
        ]
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "provider",
                    "data_type",
                    "zone",
                    "observed_at",
                    "temporal_granularity",
                    "emission_factor_type",
                    "flow_traced",
                ),
                name="unique_external_observation",
            ),
        ]

    def __str__(self):
        return (
            f"{self.provider} - "
            f"{self.zone} - "
            f"{self.observed_at:%Y-%m-%d %H:%M}"
        )