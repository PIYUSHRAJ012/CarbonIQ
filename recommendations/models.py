from django.conf import settings
from django.db import models

from core.models import TimeStampedModel

class Recommendation(TimeStampedModel):
    """
    Represents a reusable sustainability recommendation
    maintained in the CarbonIQ recommendation catalog.
    """

    class ActionType(models.TextChoices):
        SUSTAINABILITY = "SUSTAINABILITY", "Sustainability"
        OFFSET = "OFFSET", "Carbon Offset"

    title = models.CharField(
        max_length=200,
        help_text="Short title of the recommendation."
    )

    description = models.TextField(
        help_text="Detailed explanation of the recommended action."
    )

    category = models.ForeignKey(
        "carbon.ActivityCategory",
        on_delete=models.PROTECT,
        related_name="recommendations",
        blank=True,
        null=True,
        help_text=(
            "Optional activity category this recommendation primarily addresses."
        )
    )

    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
        default=ActionType.SUSTAINABILITY,
        help_text="Type of action represented by this recommendation."
    )

    priority = models.PositiveIntegerField(
        default=50,
        help_text=(
            "Base priority used when ranking recommendations. "
            "Higher values indicate greater baseline importance."
        )
    )

    applicable_segment = models.CharField(
        max_length=100,
        blank=True,
        help_text=(
            "Optional interpreted user-segment/profile descriptor "
            "for which this recommendation is particularly relevant."
        )
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this recommendation is currently available."
    )

    class Meta:
        ordering = ["-priority", "title"]
        verbose_name = "Recommendation"
        verbose_name_plural = "Recommendations"

        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["action_type"]),
            models.Index(fields=["category", "is_active"]),
        ]

    def __str__(self):
        return self.title

class UserRecommendation(TimeStampedModel):
    """
    Represents a personalized recommendation generated
    for a specific CarbonIQ user.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISMISSED = "DISMISSED", "Dismissed"
        COMPLETED = "COMPLETED", "Completed"
        SUPERSEDED = "SUPERSEDED", "Superseded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendations",
        help_text="User who received this recommendation."
    )

    recommendation = models.ForeignKey(
        Recommendation,
        on_delete=models.PROTECT,
        related_name="user_recommendations",
        help_text="Recommendation assigned to the user."
    )

    score = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text=(
            "Personalized relevance score assigned to this recommendation."
        )
    )

    reason = models.TextField(
        help_text=(
            "Explanation describing why this recommendation was "
            "generated for the user."
        )
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Current status of the personalized recommendation."
    )

    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when this recommendation was generated."
    )

    class Meta:
        ordering = ["-score", "-generated_at"]

        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-score"]),
            models.Index(fields=["recommendation", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.recommendation.title} ({self.score})"
        )