from decimal import Decimal, ROUND_HALF_UP

from django.db import transaction

from carbon.models import ActivityCategory, EmissionFactor
from carbon.services.emission_import.base import ImportedEmissionFactor


class EmissionFactorImporter:
    """
    Persists normalized emission factors into the database.

    Responsibilities:
    - Validate the target category.
    - Normalize factor precision to the database precision.
    - Detect an already-imported version.
    - Preserve existing historical factors.
    - Create new effective versions transactionally.
    """

    FACTOR_PRECISION = Decimal("0.0001")

    @classmethod
    @transaction.atomic
    def import_factor(
        cls,
        imported_factor: ImportedEmissionFactor,
    ) -> tuple[EmissionFactor, bool]:
        """
        Import one normalized emission factor.

        Returns:
            (EmissionFactor instance, created)

        created=True  -> a new version was inserted.
        created=False -> an identical version already existed.
        """

        if not isinstance(
            imported_factor,
            ImportedEmissionFactor,
        ):
            raise ValueError(
                "A valid ImportedEmissionFactor is required."
            )

        category = (
            ActivityCategory.objects
            .filter(
                name=imported_factor.category_name,
                is_active=True,
            )
            .first()
        )

        if category is None:
            raise ValueError(
                f"Active activity category "
                f"'{imported_factor.category_name}' "
                f"was not found."
            )

        if imported_factor.factor <= Decimal("0"):
            raise ValueError(
                "Emission factor must be greater than zero."
            )

        normalized_factor = imported_factor.factor.quantize(
            cls.FACTOR_PRECISION,
            rounding=ROUND_HALF_UP,
        )

        existing = (
            EmissionFactor.objects
            .filter(
                activity_category=category,
                source=imported_factor.source,
                effective_from=imported_factor.effective_from,
            )
            .order_by("-id")
            .first()
        )

        if existing is not None:
            if existing.factor == normalized_factor:
                return existing, False

            raise ValueError(
                "A factor already exists for the same "
                "category, source, and effective date, "
                "but the value is different."
            )

        # Close the currently open-ended version, if one exists.
        previous_factor = (
            EmissionFactor.objects
            .filter(
                activity_category=category,
                effective_from__lt=imported_factor.effective_from,
                effective_to__isnull=True,
            )
            .order_by("-effective_from")
            .first()
        )

        if previous_factor is not None:
            previous_factor.effective_to = (
                imported_factor.effective_from
                - imported_factor.effective_from.resolution
            )

            previous_factor.full_clean()
            previous_factor.save(
                update_fields=[
                    "effective_to",
                    "updated_at",
                ]
            )

        emission_factor = EmissionFactor(
            activity_category=category,
            factor=normalized_factor,
            source=imported_factor.source,
            effective_from=imported_factor.effective_from,
            effective_to=imported_factor.effective_to,
            is_active=True,
        )

        emission_factor.full_clean()
        emission_factor.save()

        return emission_factor, True