from decimal import Decimal

from django.db.models import Sum
from django.db.models.functions import TruncMonth, TruncWeek

from carbon.models import (
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
)


class AnalyticsAggregationService:
    """
    Provides reusable aggregation operations for CarbonIQ analytics.
    """

    @staticmethod
    def get_total_emission(user) -> Decimal:
        """
        Return the user's total completed carbon footprint in kg CO₂e.

        Only completed CarbonActivity submissions are included.
        Returns Decimal('0.0000') when the user has no completed
        footprint records.
        """

        total = (
            CarbonFootprint.objects
            .filter(
                carbon_activity__user=user,
                carbon_activity__status=CarbonActivity.Status.COMPLETED,
            )
            .aggregate(total=Sum("total_emission"))
            ["total"]
        )

        return total if total is not None else Decimal("0.0000")

    @staticmethod
    def get_monthly_emissions(user):
        """
        Return completed carbon emissions grouped by calendar month.

        Result format:
        [
            {
                "month": date,
                "total_emission": Decimal(...)
            },
            ...
        ]
        """

        return (
            CarbonFootprint.objects
            .filter(
                carbon_activity__user=user,
                carbon_activity__status=CarbonActivity.Status.COMPLETED,
            )
            .annotate(month=TruncMonth("calculated_at"))
            .values("month")
            .annotate(total_emission=Sum("total_emission"))
            .order_by("month")
        )
    
    @staticmethod
    def get_weekly_emissions(user):
        """
        Return completed carbon emissions grouped by calendar week.
        """

        return (
            CarbonFootprint.objects
            .filter(
                carbon_activity__user=user,
                carbon_activity__status=CarbonActivity.Status.COMPLETED,
            )
            .annotate(week=TruncWeek("calculated_at"))
            .values("week")
            .annotate(total_emission=Sum("total_emission"))
            .order_by("week")
        )
    
    @staticmethod
    def get_category_emissions(user):
        """
        Return completed carbon emissions grouped by activity category.

        Results are ordered from highest to lowest total emission.
        """

        return (
            ActivityEntry.objects
            .filter(
                carbon_activity__user=user,
                carbon_activity__status=CarbonActivity.Status.COMPLETED,
            )
            .values(
                "category__name",
            )
            .annotate(
                total_emission=Sum("entry_emission"),
            )
            .order_by("-total_emission")
        )