from datetime import date
from decimal import Decimal

from carbon.services.emission_import.base import ImportedEmissionFactor


class IndiaFoodSourceAdapter:
    """
    Adapter for the India-relevant food emission factors
    referenced in NABARD Working Paper 2025-1.

    The source reports production-stage GHG intensity
    in kg CO2e per kg of food.
    """

    SOURCE_NAME = (
        "NABARD Working Paper 2025-1 - "
        "Emission of Greenhouse Gases Due to Production of Food Items"
    )

    SOURCE_VERSION = "NABARD Working Paper 2025-1"

    EFFECTIVE_FROM = date(2025, 1, 1)

    FACTORS = {
        "Rice & Grain": Decimal("3.6"),
        "Legumes": Decimal("2.0"),
        "Milk": Decimal("3.2"),
        "Tofu": Decimal("3.2"),
        "Fruit": Decimal("0.9"),
        "Vegetables": Decimal("0.7"),
    }

    @classmethod
    def get_factor(
        cls,
        category_name: str,
    ) -> ImportedEmissionFactor:
        """
        Return the normalized emission factor for a supported
        food category.

        Raises:
            ValueError: If the category is not supported.
        """

        if category_name not in cls.FACTORS:
            raise ValueError(
                f"Unsupported food category: {category_name}"
            )

        return ImportedEmissionFactor(
            category_name=category_name,
            factor=cls.FACTORS[category_name],
            unit="kgCO2e/kg",
            source=cls.SOURCE_NAME,
            source_version=cls.SOURCE_VERSION,
            effective_from=cls.EFFECTIVE_FROM,
            effective_to=None,
        )

    @classmethod
    def get_all_factors(cls) -> list[ImportedEmissionFactor]:
        """
        Return all supported food emission factors.
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