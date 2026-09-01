from django.contrib import admin

from .models import (
    OffsetProject,
    OffsetRecommendation,
    Recommendation,
    UserRecommendation,
)

@admin.register(Recommendation)
class RecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "title",
        "category",
        "action_type",
        "priority",
        "applicable_segment",
        "is_active",
    )

    list_filter = (
        "action_type",
        "category",
        "is_active",
    )

    search_fields = (
        "title",
        "description",
        "applicable_segment",
    )

    ordering = (
        "-priority",
        "title",
    )

    list_editable = (
        "priority",
        "is_active",
    )


@admin.register(UserRecommendation)
class UserRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "recommendation",
        "score",
        "status",
        "generated_at",
    )

    list_filter = (
        "status",
        "recommendation__action_type",
        "recommendation__category",
    )

    search_fields = (
        "user__email",
        "recommendation__title",
        "reason",
    )

    ordering = (
        "-score",
        "-generated_at",
    )

    readonly_fields = (
        "generated_at",
    )

@admin.register(OffsetProject)
class OffsetProjectAdmin(admin.ModelAdmin):
    list_display = (
        "name",
        "registry",
        "registry_project_id",
        "country",
        "project_type",
        "status",
        "is_active",
        "source_last_verified_at",
    )

    list_filter = (
        "registry",
        "status",
        "country",
        "is_active",
    )

    search_fields = (
        "name",
        "registry_project_id",
        "registry",
        "country",
        "region",
        "project_type",
        "project_developer",
    )

    ordering = (
        "registry",
        "name",
    )

    readonly_fields = (
        "source_last_verified_at",
        "created_at",
        "updated_at",
    )


@admin.register(OffsetRecommendation)
class OffsetRecommendationAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "offset_project",
        "score",
        "indicative_tonnes",
        "status",
        "generated_at",
    )

    list_filter = (
        "status",
        "offset_project__registry",
        "offset_project__country",
    )

    search_fields = (
        "user__email",
        "user__full_name",
        "offset_project__name",
        "offset_project__registry_project_id",
        "reason",
    )

    ordering = (
        "-score",
        "-generated_at",
    )

    readonly_fields = (
        "generated_at",
        "created_at",
        "updated_at",
    )