from decimal import Decimal

from django.template.loader import render_to_string
from django.test import SimpleTestCase

from dashboard.services.insights.contracts import Insight, InsightType


class DashboardE7TemplateTests(SimpleTestCase):
    def test_sustainability_insight_is_rendered(self):
        insight = Insight(
            type=InsightType.EMISSION_DRIVER,
            title="Your largest emission driver is Diesel",
            message="Diesel contributes approximately 56.0% of your recorded carbon footprint.",
            priority=90,
            source="test",
            metric=Decimal("145.66"),
            metric_unit="kg CO2e",
        )

        html = render_to_string(
            "dashboard/dashboard.html",
            {
                "insights": (insight,),
                "total_emission": Decimal("145.66"),
                "monthly_emissions": [],
                "weekly_emissions": [],
                "category_emissions": [],
                "monthly_chart_data": [],
                "weekly_chart_data": [],
                "category_chart_data": [],
                "benchmark_resolution": None,
                "benchmark_monthly_kg": None,
                "benchmark_monthly_comparisons": (),
                "carbon_prediction": None,
                "user_segment": None,
            },
        )

        self.assertIn("Sustainability Insights", html)
        self.assertIn(insight.title, html)
        self.assertIn(insight.message, html)
        self.assertIn(insight.type.value, html)
        self.assertIn("145.66", html)

    def test_empty_insights_render_graceful_empty_state(self):
        html = render_to_string(
            "dashboard/dashboard.html",
            {
                "insights": (),
                "total_emission": Decimal("0"),
                "monthly_emissions": [],
                "weekly_emissions": [],
                "category_emissions": [],
                "monthly_chart_data": [],
                "weekly_chart_data": [],
                "category_chart_data": [],
                "benchmark_resolution": None,
                "benchmark_monthly_kg": None,
                "benchmark_monthly_comparisons": (),
                "carbon_prediction": None,
                "user_segment": None,
            },
        )

        self.assertIn("Sustainability Insights", html)
        self.assertIn(
            "No sustainability insights available yet",
            html,
        )