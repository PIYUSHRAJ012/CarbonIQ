from django.core.exceptions import ValidationError
from django.db import transaction

from carbon.models import ActivityEntry, CarbonActivity
from carbon.services.calculator import CarbonCalculationService
from carbon.services.emission import EmissionFactorService
from carbon.services.footprint import CarbonFootprintService


class CarbonSubmissionService:
    """
    Service responsible for creating a complete CarbonActivity
    submission from validated user input.
    """

    @classmethod
    @transaction.atomic
    def create_submission(cls, *, user, entries_data):
        """
        Create a CarbonActivity and fully populated ActivityEntry
        records, then calculate and persist the final footprint.

        Parameters:
            user:
                Authenticated user submitting the activity.

            entries_data:
                Iterable of dictionaries containing:
                - category
                - quantity

        Returns:
            CarbonActivity:
                The completed submission.

        Raises:
            ValidationError:
                If the user or submission data is invalid.
        """

        if user is None or not user.is_authenticated:
            raise ValidationError(
                "An authenticated user is required."
            )

        if not entries_data:
            raise ValidationError(
                "At least one activity entry is required."
            )

        carbon_activity = CarbonActivity.objects.create(
            user=user,
            status=CarbonActivity.Status.PENDING,
        )

        reference_date = carbon_activity.created_at.date()

        for entry_data in entries_data:
            category = entry_data.get("category")
            quantity = entry_data.get("quantity")

            if category is None:
                raise ValidationError(
                    "Each activity entry must have a category."
                )

            if quantity is None:
                raise ValidationError(
                    "Each activity entry must have a quantity."
                )

            emission_factor = (
                EmissionFactorService.get_active_factor(
                    category=category,
                    reference_date=reference_date,
                )
            )

            entry_emission = (
                CarbonCalculationService.calculate_emission(
                    quantity=quantity,
                    emission_factor=emission_factor,
                )
            )

            entry = ActivityEntry(
                carbon_activity=carbon_activity,
                category=category,
                emission_factor=emission_factor,
                quantity=quantity,
                emission_factor_snapshot=emission_factor.factor,
                entry_emission=entry_emission,
            )

            entry.full_clean()
            entry.save()

        CarbonFootprintService.calculate_footprint(
            carbon_activity
        )

        return carbon_activity