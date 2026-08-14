from decimal import Decimal

from django.core.exceptions import ValidationError
from django.db import transaction

from carbon.models import CarbonActivity, CarbonFootprint
from carbon.services.calculator import CarbonCalculationService
from carbon.services.emission import EmissionFactorService


class CarbonFootprintService:
    """
    Service responsible for calculating and persisting the complete
    carbon footprint for one CarbonActivity submission.
    """

    CALCULATION_VERSION = "v1.0"

    @classmethod
    def calculate_footprint(
        cls,
        carbon_activity: CarbonActivity,
    ) -> CarbonFootprint:
        """
        Calculate and persist the carbon footprint for a submission.

        The calculation itself is transactional. If it fails, all
        calculation changes are rolled back and the submission is
        subsequently marked as FAILED.
        """

        if not isinstance(carbon_activity, CarbonActivity):
            raise ValidationError(
                "A valid CarbonActivity instance is required."
            )

        entries = list(
            carbon_activity.entries.select_related(
                "category",
                "emission_factor",
            )
        )

        if not entries:
            raise ValidationError(
                "A carbon activity must contain at least one entry."
            )

        carbon_activity.status = CarbonActivity.Status.PROCESSING
        carbon_activity.save(
            update_fields=["status", "updated_at"]
        )

        try:
            with transaction.atomic():
                total_emission = Decimal("0.0000")

                reference_date = carbon_activity.created_at.date()

                for entry in entries:
                    emission_factor = (
                        EmissionFactorService.get_active_factor(
                            category=entry.category,
                            reference_date=reference_date,
                        )
                    )

                    entry_emission = (
                        CarbonCalculationService.calculate_emission(
                            quantity=entry.quantity,
                            emission_factor=emission_factor,
                        )
                    )

                    entry.emission_factor = emission_factor
                    entry.emission_factor_snapshot = emission_factor.factor
                    entry.entry_emission = entry_emission

                    entry.full_clean(
                        exclude=["carbon_activity"]
                    )

                    entry.save(
                        update_fields=[
                            "emission_factor",
                            "emission_factor_snapshot",
                            "entry_emission",
                            "updated_at",
                        ]
                    )

                    total_emission += entry_emission

                footprint, _ = CarbonFootprint.objects.update_or_create(
                    carbon_activity=carbon_activity,
                    defaults={
                        "total_emission": total_emission,
                        "calculation_version": cls.CALCULATION_VERSION,
                    },
                )

        except Exception:
            carbon_activity.status = CarbonActivity.Status.FAILED
            carbon_activity.save(
                update_fields=["status", "updated_at"]
            )
            raise

        carbon_activity.status = CarbonActivity.Status.COMPLETED
        carbon_activity.save(
            update_fields=["status", "updated_at"]
        )

        return footprint