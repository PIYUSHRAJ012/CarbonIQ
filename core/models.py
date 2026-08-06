from django.db import models


class TimeStampedModel(models.Model):
    """
    Abstract base model that provides timestamp fields
    for all inheriting models.
    """

    created_at = models.DateTimeField(
        auto_now_add=True,
        help_text="Date and time when this record was created."
    )

    updated_at = models.DateTimeField(
        auto_now=True,
        help_text="Date and time when this record was last updated."
    )

    class Meta:
        abstract = True