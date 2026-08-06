from django.contrib import admin

from .models import (
    ActivityCategory,
    EmissionFactor,
    CarbonActivity,
    ActivityEntry,
    CarbonFootprint,
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

    