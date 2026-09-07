from django.contrib import admin

from .models import (
    Achievement,
    Challenge,
    UserAchievement,
    UserChallenge,
)


@admin.register(Achievement)
class AchievementAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "name",
        "is_active",
        "created_at",
        "updated_at",
    )

    list_filter = ("is_active",)

    search_fields = (
        "code",
        "name",
        "description",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = ("name",)


@admin.register(UserAchievement)
class UserAchievementAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "achievement",
        "earned_at",
        "created_at",
    )

    list_filter = (
        "achievement",
        "earned_at",
    )

    search_fields = (
        "user__email",
        "user__username",
        "achievement__code",
        "achievement__name",
    )

    readonly_fields = (
        "earned_at",
        "created_at",
        "updated_at",
    )

    ordering = ("-earned_at",)


@admin.register(Challenge)
class ChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "code",
        "title",
        "metric",
        "target",
        "start_date",
        "end_date",
        "is_active",
    )

    list_filter = (
        "metric",
        "is_active",
        "start_date",
        "end_date",
    )

    search_fields = (
        "code",
        "title",
        "description",
    )

    readonly_fields = (
        "created_at",
        "updated_at",
    )

    ordering = (
        "start_date",
        "title",
    )


@admin.register(UserChallenge)
class UserChallengeAdmin(admin.ModelAdmin):
    list_display = (
        "user",
        "challenge",
        "progress",
        "completed",
        "completed_at",
        "created_at",
    )

    list_filter = (
        "completed",
        "challenge__metric",
    )

    search_fields = (
        "user__email",
        "user__username",
        "challenge__code",
        "challenge__title",
    )

    readonly_fields = (
        "completed_at",
        "created_at",
        "updated_at",
    )

    ordering = ("-created_at",)