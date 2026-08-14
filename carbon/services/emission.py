from datetime import date

from django.core.exceptions import ValidationError
from django.db.models import Q

from carbon.models import ActivityCategory, EmissionFactor


class EmissionFactorService:
    """
    Service responsible for retrieving the correct emission factor
    for an activity category on a specific date.
    """

    @staticmethod
    def get_active_factor(
        category: ActivityCategory,
        reference_date: date | None = None,
    ) -> EmissionFactor:
        """
        Return the emission factor applicable to the category
        on the given reference date.

        Raises:
            ValidationError: If the category is invalid or no
            applicable emission factor exists.
        """

        if not isinstance(category, ActivityCategory):
            raise ValidationError(
                "A valid ActivityCategory instance is required."
            )

        reference_date = reference_date or date.today()

        factor = (
            EmissionFactor.objects
            .filter(
                activity_category=category,
                is_active=True,
                effective_from__lte=reference_date,
            )
            .filter(
                Q(effective_to__isnull=True)
                | Q(effective_to__gte=reference_date)
            )
            .order_by("-effective_from")
            .first()
        )

        if factor is None:
            raise ValidationError(
                f"No active emission factor is available for "
                f"'{category.name}' on {reference_date}."
            )

        return factor