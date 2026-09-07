from django.conf import settings
from django.core.validators import MinValueValidator
from django.db import models

from core.models import TimeStampedModel


class Achievement(TimeStampedModel):
    """
    Represents a reusable sustainability achievement
    that can be earned by CarbonIQ users.
    """

    code = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique machine-readable achievement code.",
    )

    name = models.CharField(
        max_length=150,
        help_text="Display name of the achievement.",
    )

    description = models.TextField(
        help_text="Explanation of what the achievement represents.",
    )

    icon = models.CharField(
        max_length=100,
        blank=True,
        help_text="Optional icon identifier used by the frontend.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this achievement can currently be earned.",
    )

    class Meta:
        ordering = ["name"]
        verbose_name = "Achievement"
        verbose_name_plural = "Achievements"

        indexes = [
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return self.name


class UserAchievement(TimeStampedModel):
    """
    Records an achievement earned by a specific CarbonIQ user.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="achievements",
        help_text="User who earned the achievement.",
    )

    achievement = models.ForeignKey(
        Achievement,
        on_delete=models.PROTECT,
        related_name="user_achievements",
        help_text="Achievement earned by the user.",
    )

    earned_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the achievement was earned.",
    )

    class Meta:
        ordering = ["-earned_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "achievement"],
                name="unique_user_achievement",
            ),
        ]

        indexes = [
            models.Index(fields=["user", "-earned_at"]),
            models.Index(fields=["achievement"]),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.achievement.name}"
        )


class Challenge(TimeStampedModel):
    """
    Represents a sustainability challenge that users can participate in.
    """

    class Metric(models.TextChoices):
        EMISSION_REDUCTION = (
            "EMISSION_REDUCTION",
            "Emission Reduction",
        )
        SUSTAINABLE_ACTIONS = (
            "SUSTAINABLE_ACTIONS",
            "Sustainable Actions",
        )
        MONTHLY_IMPROVEMENT = (
            "MONTHLY_IMPROVEMENT",
            "Monthly Improvement",
        )
        LOW_EMISSION_PERIOD = (
            "LOW_EMISSION_PERIOD",
            "Low Emission Period",
        )

    code = models.CharField(
        max_length=100,
        unique=True,
        help_text="Unique machine-readable challenge code.",
    )

    title = models.CharField(
        max_length=200,
        help_text="Display title of the challenge.",
    )

    description = models.TextField(
        help_text="Explanation of the challenge objective.",
    )

    metric = models.CharField(
        max_length=50,
        choices=Metric.choices,
        help_text="Measurement used to determine challenge progress.",
    )

    target = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Target value required to complete the challenge.",
    )

    start_date = models.DateField(
        help_text="Date from which the challenge is available.",
    )

    end_date = models.DateField(
        help_text="Date after which the challenge expires.",
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this challenge is currently available.",
    )

    class Meta:
        ordering = ["start_date", "title"]
        verbose_name = "Challenge"
        verbose_name_plural = "Challenges"

        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["metric"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(end_date__gte=models.F("start_date")),
                name="challenge_valid_date_range",
            ),
        ]

    def __str__(self):
        return self.title


class UserChallenge(TimeStampedModel):
    """
    Represents a user's participation and validated progress
    in a sustainability challenge.
    """

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="challenges",
        help_text="User participating in the challenge.",
    )

    challenge = models.ForeignKey(
        Challenge,
        on_delete=models.PROTECT,
        related_name="user_challenges",
        help_text="Challenge joined by the user.",
    )

    progress = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        default=0,
        help_text=(
            "Validated challenge progress calculated by the "
            "server-side gamification services."
        ),
    )

    completed = models.BooleanField(
        default=False,
        help_text="Whether the user has completed the challenge.",
    )

    completed_at = models.DateTimeField(
        blank=True,
        null=True,
        help_text="Timestamp when the challenge was completed.",
    )

    class Meta:
        ordering = ["-created_at"]

        constraints = [
            models.UniqueConstraint(
                fields=["user", "challenge"],
                name="unique_user_challenge",
            ),
        ]

        indexes = [
            models.Index(fields=["user", "completed"]),
            models.Index(fields=["challenge", "completed"]),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.challenge.title}"
        )