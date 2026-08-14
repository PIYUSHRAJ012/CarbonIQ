from decimal import Decimal, ROUND_HALF_UP

from django.core.exceptions import ValidationError

from carbon.models import EmissionFactor


class CarbonCalculationService:
    """
    Service responsible for calculating carbon emissions
    from a quantity and an emission factor.
    """

    EMISSION_PRECISION = Decimal("0.0001")

    @classmethod
    def calculate_emission(
        cls,
        quantity: Decimal,
        emission_factor: EmissionFactor,
    ) -> Decimal:
        """
        Calculate carbon emission using:

            emission = quantity × emission factor

        Returns:
            Decimal value rounded to 4 decimal places.

        Raises:
            ValidationError: If the quantity or emission factor
            is invalid.
        """

        if quantity is None:
            raise ValidationError("Quantity is required.")

        if not isinstance(quantity, Decimal):
            quantity = Decimal(str(quantity))

        if quantity < Decimal("0"):
            raise ValidationError("Quantity cannot be negative.")

        if not isinstance(emission_factor, EmissionFactor):
            raise ValidationError(
                "A valid EmissionFactor instance is required."
            )

        factor = emission_factor.factor

        if factor is None:
            raise ValidationError(
                "Emission factor value is required."
            )

        if factor < Decimal("0"):
            raise ValidationError(
                "Emission factor cannot be negative."
            )

        emission = quantity * factor

        return emission.quantize(
            cls.EMISSION_PRECISION,
            rounding=ROUND_HALF_UP,
        )