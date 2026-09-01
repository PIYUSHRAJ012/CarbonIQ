from django.conf import settings
from django.core.validators import MinValueValidator
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


class OffsetProject(TimeStampedModel):
    """
    Represents an externally registered carbon-offset project
    imported into the CarbonIQ local project catalog.

    CarbonIQ stores normalized registry metadata for discovery
    and recommendation. The external registry remains the
    authoritative source for project information.
    """

    class ProjectStatus(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        INACTIVE = "INACTIVE", "Inactive"
        COMPLETED = "COMPLETED", "Completed"
        SUSPENDED = "SUSPENDED", "Suspended"
        UNKNOWN = "UNKNOWN", "Unknown"

    name = models.CharField(
        max_length=255,
        help_text="Registered project name."
    )

    description = models.TextField(
        blank=True,
        help_text="Project description obtained from the source registry."
    )

    project_type = models.CharField(
        max_length=150,
        blank=True,
        help_text="Project type or activity classification."
    )

    country = models.CharField(
        max_length=100,
        blank=True,
        help_text="Country where the project is located."
    )

    region = models.CharField(
        max_length=150,
        blank=True,
        help_text="State, province, region, or other geographic subdivision."
    )

    registry = models.CharField(
        max_length=150,
        help_text="External registry name."
    )

    registry_project_id = models.CharField(
        max_length=150,
        help_text="Project identifier assigned by the external registry."
    )

    registry_url = models.URLField(
        max_length=500,
        help_text="Public URL of the project in the external registry."
    )

    standard = models.CharField(
        max_length=150,
        blank=True,
        help_text="Certification or carbon standard associated with the project."
    )

    status = models.CharField(
        max_length=20,
        choices=ProjectStatus.choices,
        default=ProjectStatus.UNKNOWN,
        help_text="Normalized project status from the source registry."
    )

    project_scale = models.CharField(
        max_length=100,
        blank=True,
        help_text="Project scale as reported by the source registry."
    )

    annual_estimated_credits = models.DecimalField(
        max_digits=14,
        decimal_places=2,
        blank=True,
        null=True,
        validators=[MinValueValidator(0)],
        help_text=(
            "Annual estimated carbon credits reported by the registry, "
            "when available."
        )
    )

    sdg_impacts = models.JSONField(
        default=list,
        blank=True,
        help_text=(
            "Structured SDG impact information reported by the source registry."
        )
    )

    project_developer = models.CharField(
        max_length=255,
        blank=True,
        help_text="Project developer or implementing organization."
    )

    certification_documents_url = models.URLField(
        max_length=500,
        blank=True,
        help_text="Public certification or project-document URL, when available."
    )

    source_last_verified_at = models.DateTimeField(
        help_text="Timestamp when CarbonIQ last verified this project against the source."
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this project is currently eligible for recommendations."
    )

    class Meta:
        ordering = ["name"]

        verbose_name = "Offset Project"
        verbose_name_plural = "Offset Projects"

        constraints = [
            models.UniqueConstraint(
                fields=["registry", "registry_project_id"],
                name="unique_offset_registry_project",
            ),
        ]

        indexes = [
            models.Index(fields=["registry"]),
            models.Index(fields=["registry_project_id"]),
            models.Index(fields=["country"]),
            models.Index(fields=["project_type"]),
            models.Index(fields=["status"]),
            models.Index(fields=["is_active"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.registry_project_id})"


class OffsetRecommendation(TimeStampedModel):
    """
    Represents a personalized offset-project recommendation
    generated for a CarbonIQ user.

    `indicative_tonnes` is a snapshot of the offset requirement
    calculated at recommendation-generation time. It is not a
    purchase quantity, price, or retirement instruction.
    """

    class Status(models.TextChoices):
        ACTIVE = "ACTIVE", "Active"
        DISMISSED = "DISMISSED", "Dismissed"
        COMPLETED = "COMPLETED", "Completed"
        SUPERSEDED = "SUPERSEDED", "Superseded"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="offset_recommendations",
        help_text="User who received this offset recommendation."
    )

    offset_project = models.ForeignKey(
        OffsetProject,
        on_delete=models.PROTECT,
        related_name="recommendations",
        help_text="Offset project recommended to the user."
    )

    score = models.DecimalField(
        max_digits=8,
        decimal_places=4,
        help_text="Personalized relevance score for this project."
    )

    reason = models.TextField(
        help_text=(
            "Explanation describing why this offset project "
            "was recommended to the user."
        )
    )

    indicative_tonnes = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text=(
            "Indicative offset requirement in tonnes CO₂e captured "
            "at recommendation-generation time."
        )
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.ACTIVE,
        help_text="Current lifecycle status of this offset recommendation."
    )

    generated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when this offset recommendation was generated."
    )

    class Meta:
        ordering = ["-score", "-generated_at"]

        verbose_name = "Offset Recommendation"
        verbose_name_plural = "Offset Recommendations"

        indexes = [
            models.Index(fields=["user", "status"]),
            models.Index(fields=["user", "-score"]),
            models.Index(fields=["offset_project", "status"]),
        ]

    def __str__(self):
        return (
            f"{self.user.email} - "
            f"{self.offset_project.name} ({self.score})"
        )