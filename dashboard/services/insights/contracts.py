from dataclasses import dataclass
from decimal import Decimal
from enum import StrEnum


class InsightType(StrEnum):
    """
    Supported categories of advanced sustainability insights.
    """

    TREND = "trend"
    EMISSION_DRIVER = "emission_driver"
    PREDICTION = "prediction"
    SEGMENT = "segment"
    BENCHMARK = "benchmark"
    ENVIRONMENTAL_CONTEXT = "environmental_context"
    ACTION_PRIORITY = "action_priority"


@dataclass(frozen=True, slots=True)
class Insight:
    """
    Immutable domain object representing one user-facing insight.
    """

    type: InsightType
    title: str
    message: str
    priority: int
    source: str
    metric: Decimal | None = None
    metric_unit: str | None = None