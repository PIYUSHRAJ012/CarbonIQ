from datetime import date
from decimal import Decimal

from carbon.services.emission_import.base import ImportedEmissionFactor


class IndiaFuelSourceAdapter:
    """
    Adapter for India-specific petrol and diesel fuel factors.

    Source:
    Bureau of Energy Efficiency (India) - CAFE 2027
    fuel consumption / CO2 relationship.

    Note:
    The normalized kgCO2/litre values are derived from the
    BEE-published relationship and are therefore an
    application-level conversion, not directly quoted as
    kgCO2/litre in the source.
    """

    SOURCE_NAME = (
        "Bureau of Energy Efficiency (India) - "
        "CAFE 2027 fuel consumption/CO2 relationship"
    )

    SOURCE_VERSION = "CAFE 2027"

    PETROL_FACTOR = Decimal("2.37135")
    DIESEL_FACTOR = Decimal("2.64831")

    EFFECTIVE_FROM = date(2026, 4, 1)

    @classmethod
    def get_petrol_factor(
        cls,
    ) -> ImportedEmissionFactor:
        """
        Return the normalized petrol factor.
        """

        return ImportedEmissionFactor(
            category_name="Petrol",
            factor=cls.PETROL_FACTOR,
            unit="kgCO2/litre",
            source=cls.SOURCE_NAME,
            source_version=cls.SOURCE_VERSION,
            effective_from=cls.EFFECTIVE_FROM,
            effective_to=None,
        )

    @classmethod
    def get_diesel_factor(
        cls,
    ) -> ImportedEmissionFactor:
        """
        Return the normalized diesel factor.
        """

        return ImportedEmissionFactor(
            category_name="Diesel",
            factor=cls.DIESEL_FACTOR,
            unit="kgCO2/litre",
            source=cls.SOURCE_NAME,
            source_version=cls.SOURCE_VERSION,
            effective_from=cls.EFFECTIVE_FROM,
            effective_to=None,
        )

    @classmethod
    def get_factors(
        cls,
    ) -> list[ImportedEmissionFactor]:
        """
        Return all emission factors provided by this source.
        """

        return [
            cls.get_petrol_factor(),
            cls.get_diesel_factor(),
        ]