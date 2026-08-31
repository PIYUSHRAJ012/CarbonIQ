from django.contrib import admin

from .models import Recommendation, UserRecommendation


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