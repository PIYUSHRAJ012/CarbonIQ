from dataclasses import dataclass
from datetime import date
from decimal import Decimal


@dataclass(frozen=True)
class ImportedEmissionFactor:
    """
    Normalized emission-factor representation produced by
    every external source adapter.
    """

    category_name: str
    factor: Decimal
    unit: str
    source: str
    source_version: str
    effective_from: date
    effective_to: date | None = None