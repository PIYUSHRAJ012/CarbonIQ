from decimal import Decimal

from django.test import SimpleTestCase

from .contracts import Insight, InsightType
from .signals import InsightSignals
from .service import build_insights


class BuildInsightsTests(SimpleTestCase):
    def test_empty_signals_return_no_insights(self):
        result = build_insights(InsightSignals())

        self.assertEqual(result, ())

    def test_generated_insights_are_ranked(self):
        signals = InsightSignals(
            current_total_emission=Decimal("100"),
            top_category="Transport",
            top_category_emission=Decimal("60"),
        )

        result = build_insights(signals)

        self.assertTrue(result)
        self.assertEqual(
            list(result),
            sorted(
                result,
                key=lambda insight: (
                    -insight.priority,
                    -(1 if insight.metric is not None else 0),
                    insight.title.lower(),
                    insight.message.lower(),
                ),
            ),
        )

    def test_service_returns_insight_objects(self):
        signals = InsightSignals(
            current_total_emission=Decimal("100"),
            top_category="Transport",
            top_category_emission=Decimal("60"),
        )

        result = build_insights(signals)

        self.assertTrue(result)
        self.assertTrue(all(isinstance(item, Insight) for item in result))

    def test_action_priority_remains_above_lower_priority_insights(self):
        signals = InsightSignals(
            current_total_emission=Decimal("100"),
            top_category="Transport",
            top_category_emission=Decimal("60"),
        )

        result = build_insights(signals)

        action_insights = [
            insight
            for insight in result
            if insight.type == InsightType.ACTION_PRIORITY
        ]

        if action_insights and len(result) > 1:
            self.assertEqual(result[0].type, InsightType.ACTION_PRIORITY)

    def test_service_does_not_fabricate_prediction(self):
        signals = InsightSignals(
            current_total_emission=Decimal("100"),
            top_category="Transport",
            top_category_emission=Decimal("60"),
            prediction=None,
        )

        result = build_insights(signals)

        prediction_insights = [
            insight
            for insight in result
            if insight.type == InsightType.PREDICTION
        ]

        self.assertEqual(prediction_insights, [])

    def test_service_does_not_fabricate_segment(self):
        signals = InsightSignals(
            current_total_emission=Decimal("100"),
            top_category="Transport",
            top_category_emission=Decimal("60"),
            user_segment=None,
        )

        result = build_insights(signals)

        segment_insights = [
            insight
            for insight in result
            if insight.type == InsightType.SEGMENT
        ]

        self.assertEqual(segment_insights, [])