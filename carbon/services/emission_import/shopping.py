from datetime import date
from decimal import Decimal

from carbon.services.emission_import.base import ImportedEmissionFactor


class IndiaShoppingSourceAdapter:
    """
    Adapter for India-specific household consumption
    emission intensities for clothing and footwear.

    Source:
    India-specific household carbon-footprint research
    using Indian household consumption expenditure data.
    """

    EFFECTIVE_FROM = date(2005, 1, 1)

    FACTORS = {
        "Clothing": {
            "factor": Decimal("0.0411"),
            "source": (
                "India-specific household carbon footprint study - "
                "Readymade Garments"
            ),
        },
        "Footwear": {
            "factor": Decimal("0.0268"),
            "source": (
                "India-specific household carbon footprint study - "
                "Leather Footwear"
            ),
        },
    }

    SOURCE_VERSION = "Indian household expenditure study"

    @classmethod
    def get_factor(
        cls,
        category_name: str,
    ) -> ImportedEmissionFactor:
        """
        Return the normalized factor for a supported
        shopping category.
        """

        if category_name not in cls.FACTORS:
            raise ValueError(
                f"Unsupported shopping category: {category_name}"
            )

        factor_data = cls.FACTORS[category_name]

        return ImportedEmissionFactor(
            category_name=category_name,
            factor=factor_data["factor"],
            unit="kgCO2e/₹",
            source=factor_data["source"],
            source_version=cls.SOURCE_VERSION,
            effective_from=cls.EFFECTIVE_FROM,
            effective_to=None,
        )

    @classmethod
    def get_all_factors(
        cls,
    ) -> list[ImportedEmissionFactor]:
        """
        Return all supported shopping factors.
        """

        return [
            cls.get_factor(category_name)
            for category_name in cls.FACTORS
        ]

    @classmethod
    def get_factors(
        cls,
    ) -> list[ImportedEmissionFactor]:
        """
        Return all emission factors provided by this source.
        """

        return cls.get_all_factors()