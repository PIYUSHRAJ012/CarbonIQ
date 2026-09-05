from analytics.services.aggregation import AnalyticsAggregationService
from carbon.services.comparison import get_user_monthly_benchmark_comparison
from ml.services.prediction import (
    PredictionServiceError,
    predict_next_month_carbon,
)
from ml.services.segmentation import SegmentationPredictionError
from ml.services.segmentation_profile import (
    UserSegmentProfileError,
    get_user_segment_profile,
)

class DashboardService:
    """
    Builds the data context required by the CarbonIQ dashboard.
    """

    @staticmethod
    def get_dashboard_data(user):
        """
        Return all dashboard data in both display-friendly and
        JSON-safe formats.
        """

        monthly_emissions = list(
            AnalyticsAggregationService.get_monthly_emissions(user)
        )

        weekly_emissions = list(
            AnalyticsAggregationService.get_weekly_emissions(user)
        )

        category_emissions = list(
            AnalyticsAggregationService.get_category_emissions(user)
        )

        try:
            benchmark_comparison = get_user_monthly_benchmark_comparison(user)
        except ValueError:
            benchmark_comparison = None

        # E2 Machine Learning
        try:
            carbon_prediction = predict_next_month_carbon(user.id)
        except PredictionServiceError:
            carbon_prediction = None

        try:
            user_segment = get_user_segment_profile(user.id)
        except (UserSegmentProfileError, SegmentationPredictionError):
            user_segment = None

        return {
            "total_emission": (
                AnalyticsAggregationService.get_total_emission(user)
            ),

            # Existing table data
            "monthly_emissions": monthly_emissions,
            "weekly_emissions": weekly_emissions,
            "category_emissions": category_emissions,

            # Chart-ready data
            "monthly_chart_data": [
                {
                    "label": item["month"].strftime("%B %Y"),
                    "value": float(item["total_emission"]),
                }
                for item in monthly_emissions
            ],

            "weekly_chart_data": [
                {
                    "label": item["week"].strftime("%d %b %Y"),
                    "value": float(item["total_emission"]),
                }
                for item in weekly_emissions
            ],

            "category_chart_data": [
                {
                    "label": item["category__name"],
                    "value": float(item["total_emission"]),
                }
                for item in category_emissions
            ],

            # E4 Benchmark comparison
            "benchmark_comparison": benchmark_comparison,
            "benchmark_resolution": (
                benchmark_comparison.benchmark_resolution
                if benchmark_comparison
                else None
            ),
            "benchmark_monthly_kg": (
                benchmark_comparison.benchmark_monthly_kg
                if benchmark_comparison
                else None
            ),
            "benchmark_monthly_comparisons": (
                benchmark_comparison.personal_monthly_comparisons
                if benchmark_comparison
                else ()
            ),
                        # E2 Machine Learning
            "carbon_prediction": carbon_prediction,
            "user_segment": user_segment,
        }