from datetime import date
from decimal import Decimal

from carbon.services.emission_import.base import ImportedEmissionFactor


class IndiaTransportSourceAdapter:
    """
    Adapter for the India-specific default passenger-car
    transportation emission factor.

    Source:
    Ministry of Environment, Forest and Climate Change,
    Government of India — Low Carbon Lifestyles.
    """

    SOURCE_NAME = (
        "Ministry of Environment, Forest and Climate Change "
        "(India) - Low Carbon Lifestyles"
    )

    SOURCE_VERSION = "Low Carbon Lifestyles - 2016"

    FACTOR_G_CO2_PER_KM = Decimal("126.37")

    EFFECTIVE_FROM = date(2016, 1, 1)

    @classmethod
    def get_default_transport_factor(
        cls,
    ) -> ImportedEmissionFactor:
        """
        Return the India-specific default transportation factor.
        """

        factor = (
            cls.FACTOR_G_CO2_PER_KM
            / Decimal("1000")
        )

        return ImportedEmissionFactor(
            category_name="Transportation",
            factor=factor,
            unit="kgCO2/km",
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
            cls.get_default_transport_factor()
        ]