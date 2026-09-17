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
from dashboard.services.insights.signals import InsightSignals
from dashboard.services.insights.service import build_insights
from gamification.services.engagement import build_engagement_snapshot


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
            benchmark_comparison = (
                get_user_monthly_benchmark_comparison(user)
            )
        except ValueError:
            benchmark_comparison = None

        # E2 Machine Learning
        try:
            carbon_prediction = predict_next_month_carbon(user.id)
        except PredictionServiceError:
            carbon_prediction = None

        try:
            user_segment = get_user_segment_profile(user.id)
        except (
            UserSegmentProfileError,
            SegmentationPredictionError,
        ):
            user_segment = None

        insight_signals = InsightSignals(
            current_total_emission=(
                AnalyticsAggregationService.get_total_emission(user)
            ),
            monthly_emissions=tuple(monthly_emissions),
            weekly_emissions=tuple(weekly_emissions),
            category_emissions=tuple(category_emissions),
            top_category=(
                category_emissions[0]["category__name"]
                if category_emissions
                else None
            ),
            top_category_emission=(
                category_emissions[0]["total_emission"]
                if category_emissions
                else None
            ),
            prediction=carbon_prediction,
            user_segment=user_segment,
            benchmark=benchmark_comparison,
        )

        insights = build_insights(insight_signals)

        # E8 Gamification & Engagement
        gamification = build_engagement_snapshot(user)

        # ------------------------------------------------------------------
        # E2 ML visualization data
        # ------------------------------------------------------------------

        # Existing monthly chart data.
        monthly_chart_data = [
            {
                "label": item["month"].strftime("%B %Y"),
                "value": float(item["total_emission"]),
            }
            for item in monthly_emissions
        ]

        # Random Forest prediction chart.
        #
        # The actual series contains the user's historical monthly
        # emissions. The predicted series contains the last actual point
        # and then the next-month prediction so Chart.js can draw a
        # continuous transition into the prediction.
        prediction_chart_data = None

        if carbon_prediction:
            actual_labels = [
                item["label"]
                for item in monthly_chart_data
            ]

            actual_values = [
                item["value"]
                for item in monthly_chart_data
            ]

            prediction_label = (
                carbon_prediction.target_period.strftime(
                    "%B %Y"
                )
            )

            chart_labels = [
                *actual_labels,
                prediction_label,
            ]

            chart_actual_values = [
                *actual_values,
                None,
            ]

            if actual_values:
                chart_predicted_values = (
                    [None] * (len(actual_values) - 1)
                    + [
                        actual_values[-1],
                        float(
                            carbon_prediction.predicted_emission
                        ),
                    ]
                )
            else:
                chart_predicted_values = [
                    float(
                        carbon_prediction.predicted_emission
                    )
                ]

            prediction_chart_data = {
                "labels": chart_labels,
                "actual": chart_actual_values,
                "predicted": chart_predicted_values,
            }

        # K-Means / behavioural-profile chart.
        #
        # domain_scores already come from the existing segmentation
        # interpretation layer. We only convert them into JSON-safe,
        # chart-ready values and mark the user's dominant domain.
        segment_chart_data = None

        if user_segment:
            segment_chart_data = [
                {
                    "label": domain.replace(
                        "_",
                        " ",
                    ).title(),
                    "value": float(score),
                    "is_dominant": (
                        domain
                        == user_segment.dominant_domain
                    ),
                }
                for domain, score in sorted(
                    user_segment.domain_scores.items(),
                    key=lambda item: item[1],
                    reverse=True,
                )
            ]

        return {
            "total_emission": (
                AnalyticsAggregationService.get_total_emission(user)
            ),

            # Existing table data
            "monthly_emissions": monthly_emissions,
            "weekly_emissions": weekly_emissions,
            "category_emissions": category_emissions,

            # Chart-ready data
            "monthly_chart_data": monthly_chart_data,

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

            # E2 ML chart data
            "prediction_chart_data": prediction_chart_data,
            "segment_chart_data": segment_chart_data,

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

            # E7 Advanced Sustainability Insights
            "insights": insights,

            # E8 Gamification & Engagement
            "gamification": gamification,
        }