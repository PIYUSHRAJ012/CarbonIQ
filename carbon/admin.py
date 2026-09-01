from django.contrib import admin

from .models import (
    ActivityCategory,
    EmissionFactor,
    CarbonActivity,
    ActivityEntry,
    CarbonFootprint,
    UserLocation,
    CarbonBenchmark,
)

@admin.register(ActivityEntry)
class ActivityEntryAdmin(admin.ModelAdmin):
    list_display = (
        "carbon_activity",
        "category",
        "quantity",
        "entry_emission",
    )

    list_filter = (
        "category",
    )

    search_fields = (
        "carbon_activity__user__email",
        "category__name",
    )

    readonly_fields = (
        "entry_emission",
        "emission_factor_snapshot",
    )

@admin.register(EmissionFactor)
class EmissionFactorAdmin(admin.ModelAdmin):
    list_display = (
        "activity_category",
        "factor",
        "effective_from",
        "effective_to",
        "is_active",
    )

    list_filter = (
        "activity_category",
        "is_active",
    )

    search_fields = (
        "activity_category__name",
        "source",
    )

    ordering = (
        "activity_category",
        "-effective_from",
    )

@admin.register(CarbonActivity)
class CarbonActivityAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "status",
        "created_at",
    )

    list_filter = (
        "status",
    )

    search_fields = (
        "user__email",
    )

    ordering = (
        "-created_at",
    )

@admin.register(CarbonFootprint)
class CarbonFootprintAdmin(admin.ModelAdmin):
    list_display = (
        "carbon_activity",
        "total_emission",
        "calculated_at",
        "calculation_version",
    )

    ordering = (
        "-calculated_at",
    )

    readonly_fields = (
        "total_emission",
        "calculated_at",
        "calculation_version",
    )

@admin.register(ActivityCategory)
class ActivityCategoryAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "unit",
        "display_order",
        "is_active",
    )

    list_filter = (
        "is_active",
    )

    search_fields = (
        "name",
    )

    ordering = (
        "display_order",
        "name",
    )

@admin.register(UserLocation)
class UserLocationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "state",
        "district",
        "created_at",
        "updated_at",
    )

    list_filter = (
        "state",
    )

    search_fields = (
        "user__email",
        "user__full_name",
        "state",
        "district",
    )

    ordering = (
        "state",
        "district",
    )

@admin.register(CarbonBenchmark)
class CarbonBenchmarkAdmin(admin.ModelAdmin):
    list_display = (
        "scope",
        "state",
        "district",
        "reference_period",
        "value",
        "unit",
        "source",
        "is_active",
    )

    list_filter = (
        "scope",
        "state",
        "is_active",
        "population_basis",
    )

    search_fields = (
        "state",
        "district",
        "source",
        "source_reference",
        "reference_period",
    )

    ordering = (
        "scope",
        "state",
        "district",
        "-reference_period",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )