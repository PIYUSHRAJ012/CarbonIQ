from datetime import date
from decimal import Decimal

from carbon.services.emission_import.base import ImportedEmissionFactor


class IndiaWasteSourceAdapter:
    """
    Adapter for the India-specific default organic-waste
    emission factor.

    Source:
    Ministry of Environment, Forest and Climate Change,
    Government of India — Low Carbon Lifestyles.
    """

    SOURCE_NAME = (
        "Ministry of Environment, Forest and Climate Change "
        "(India) - Low Carbon Lifestyles"
    )

    SOURCE_VERSION = "Low Carbon Lifestyles"

    FACTOR = Decimal("0.32")

    EFFECTIVE_FROM = date(2016, 1, 1)

    @classmethod
    def get_default_waste_factor(
        cls,
    ) -> ImportedEmissionFactor:
        """
        Return the default organic-waste composting factor.

        Factor:
            0.32 kg CO2e/kg waste
        """

        return ImportedEmissionFactor(
            category_name="Waste",
            factor=cls.FACTOR,
            unit="kgCO2e/kg",
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
                cls.get_default_waste_factor()
            ]