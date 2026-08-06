from django.db import models

from core.models import TimeStampedModel

from django.core.validators import MinValueValidator

from django.conf import settings

from django.core.exceptions import ValidationError

class ActivityCategory(TimeStampedModel):
    """
    Represents a category of carbon-emitting activity,
    such as Electricity, Transport, Food, etc.
    """

    name = models.CharField(
        max_length=100,
        unique=True,
        help_text="Name of the activity category."
    )

    description = models.TextField(
        blank=True,
        help_text="Optional description of the category."
    )

    unit = models.CharField(
        max_length=50,
        help_text="Measurement unit (e.g. kWh, km, litre)."
    )

    display_order = models.PositiveIntegerField(
        default=0,
        help_text="Controls the order in which categories are displayed."
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this category is available for users."
    )

    class Meta:
        ordering = ["display_order", "name"]
        verbose_name = "Activity Category"
        verbose_name_plural = "Activity Categories"

        indexes = [
            models.Index(fields=["is_active"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=models.Q(display_order__gte=0),
                name="activity_category_display_order_gte_0",
            ),
        ]

    def __str__(self):
        return self.name

class EmissionFactor(TimeStampedModel):
    """
    Stores emission factors for different activity categories.
    Supports historical versioning.
    """

    activity_category = models.ForeignKey(
        ActivityCategory,
        on_delete=models.PROTECT,
        related_name="emission_factors",
        help_text="Activity category associated with this emission factor."
    )

    factor = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Emission factor value."
    )

    source = models.CharField(
        max_length=255,
        help_text="Source of this emission factor."
    )

    effective_from = models.DateField(
        help_text="Date from which this factor becomes valid."
    )

    effective_to = models.DateField(
        blank=True,
        null=True,
        help_text="Date until which this factor remains valid."
    )

    is_active = models.BooleanField(
        default=True,
        help_text="Whether this emission factor is currently active."
    )

    def clean(self):
        super().clean()

        if (
            self.effective_to is not None
            and self.effective_to < self.effective_from
        ):
            raise ValidationError(
                {
                    "effective_to": (
                        "Effective end date cannot be earlier "
                        "than the effective start date."
                    )
                }
            )

    class Meta:
        ordering = ["activity_category", "-effective_from"]
        verbose_name = "Emission Factor"
        verbose_name_plural = "Emission Factors"

        indexes = [
            models.Index(fields=["is_active"]),
            models.Index(fields=["effective_from"]),
        ]

        constraints = [
            models.CheckConstraint(
                condition=(
                    models.Q(effective_to__isnull=True)
                    | models.Q(effective_to__gte=models.F("effective_from"))
                ),
                name="emission_factor_valid_date_range",
            ),
        ]

    def __str__(self):
        return (
            f"{self.activity_category.name} - "
            f"{self.factor} kg CO₂e/{self.activity_category.unit}"
        )

class CarbonActivity(TimeStampedModel):
    """
    Represents one carbon footprint submission
    made by a user.
    """

    class Status(models.TextChoices):
        PENDING = "PENDING", "Pending"
        PROCESSING = "PROCESSING", "Processing"
        COMPLETED = "COMPLETED", "Completed"
        FAILED = "FAILED", "Failed"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="carbon_activities",
        help_text="User who submitted this activity."
    )

    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.PENDING,
        help_text="Processing status of this submission."
    )

    notes = models.TextField(
        blank=True,
        help_text="Optional notes for this submission."
    )

    class Meta:
        ordering = ["-created_at"]
        verbose_name = "Carbon Activity"
        verbose_name_plural = "Carbon Activities"

        indexes = [
            models.Index(fields=["status"]),
        ]

    def __str__(self):
        return f"{self.user.email} - {self.created_at:%Y-%m-%d %H:%M}"

class ActivityEntry(TimeStampedModel):
    """
    Represents one activity item inside
    a carbon activity submission.
    """

    carbon_activity = models.ForeignKey(
        CarbonActivity,
        on_delete=models.CASCADE,
        related_name="entries",
        help_text="Parent carbon activity submission."
    )

    category = models.ForeignKey(
        ActivityCategory,
        on_delete=models.PROTECT,
        related_name="activity_entries",
        help_text="Category selected by the user."
    )

    emission_factor = models.ForeignKey(
        EmissionFactor,
        on_delete=models.PROTECT,
        related_name="activity_entries",
        help_text="Emission factor used."
    )

    quantity = models.DecimalField(
        max_digits=12,
        decimal_places=2,
        validators=[MinValueValidator(0)],
        help_text="Quantity entered by the user."
    )

    emission_factor_snapshot = models.DecimalField(
        max_digits=10,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Snapshot of the emission factor used."
    )

    entry_emission = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Calculated emission for this activity."
    )

    def clean(self):
        super().clean()

        if (
            self.emission_factor
            and self.category
            and self.emission_factor.activity_category != self.category
        ):
            raise ValidationError(
                {
                    "emission_factor": (
                        "Selected emission factor does not belong "
                        "to the selected activity category."
                    )
                }
            )

    class Meta:
        ordering = ["id"]
        verbose_name = "Activity Entry"
        verbose_name_plural = "Activity Entries"

    def __str__(self):
        return (
            f"{self.carbon_activity.user.email} - "
            f"{self.category.name}"
        )

class CarbonFootprint(TimeStampedModel):
    """
    Stores the calculated carbon footprint summary
    for a single carbon activity submission.
    """

    carbon_activity = models.OneToOneField(
        CarbonActivity,
        on_delete=models.CASCADE,
        related_name="carbon_footprint",
        help_text="Carbon activity associated with this footprint."
    )

    total_emission = models.DecimalField(
        max_digits=12,
        decimal_places=4,
        validators=[MinValueValidator(0)],
        help_text="Total carbon emission (kg CO₂e)."
    )

    calculated_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Timestamp when the footprint was calculated."
    )

    calculation_version = models.CharField(
        max_length=20,
        default="v1.0",
        help_text="Version of the calculation algorithm."
    )

    class Meta:
        verbose_name = "Carbon Footprint"
        verbose_name_plural = "Carbon Footprints"

    def __str__(self):
        return (
            f"{self.carbon_activity.user.email} - "
            f"{self.total_emission} kg CO₂e"
        )
