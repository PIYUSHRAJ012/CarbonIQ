from django.contrib import admin

from .models import ExternalEnvironmentalObservation


@admin.register(ExternalEnvironmentalObservation)
class ExternalEnvironmentalObservationAdmin(admin.ModelAdmin):
    list_display = (
        "provider",
        "data_type",
        "zone",
        "value",
        "unit",
        "observed_at",
        "is_estimated",
        "temporal_granularity",
    )

    list_filter = (
        "provider",
        "data_type",
        "zone",
        "is_estimated",
        "temporal_granularity",
        "emission_factor_type",
        "flow_traced",
    )

    search_fields = (
        "provider",
        "zone",
        "source_url",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "-observed_at",
    )