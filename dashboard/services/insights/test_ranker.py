from decimal import Decimal

from django.test import SimpleTestCase

from .contracts import Insight, InsightType
from .ranker import rank_insights


class RankInsightsTests(SimpleTestCase):
    def _insight(
        self,
        *,
        title: str,
        priority: int,
        metric: Decimal | None = None,
        message: str = "Test message",
    ) -> Insight:
        return Insight(
            type=InsightType.TREND,
            title=title,
            message=message,
            priority=priority,
            source="test",
            metric=metric,
            metric_unit="kg CO2",
        )

    def test_higher_priority_comes_first(self):
        low = self._insight(title="Low", priority=20)
        high = self._insight(title="High", priority=90)

        result = rank_insights((low, high))

        self.assertEqual(
            [insight.title for insight in result],
            ["High", "Low"],
        )

    def test_metric_evidence_breaks_priority_tie(self):
        without_metric = self._insight(
            title="Without metric",
            priority=50,
            metric=None,
        )
        with_metric = self._insight(
            title="With metric",
            priority=50,
            metric=Decimal("42.5"),
        )

        result = rank_insights((without_metric, with_metric))

        self.assertEqual(
            [insight.title for insight in result],
            ["With metric", "Without metric"],
        )

    def test_title_breaks_complete_tie_deterministically(self):
        second = self._insight(title="Second", priority=50)
        first = self._insight(title="First", priority=50)

        result = rank_insights((second, first))

        self.assertEqual(
            [insight.title for insight in result],
            ["First", "Second"],
        )

    def test_message_breaks_title_tie_deterministically(self):
        later_message = self._insight(
            title="Same",
            priority=50,
            message="Zebra",
        )
        earlier_message = self._insight(
            title="Same",
            priority=50,
            message="Apple",
        )

        result = rank_insights((later_message, earlier_message))

        self.assertEqual(
            [insight.message for insight in result],
            ["Apple", "Zebra"],
        )

    def test_empty_input_returns_empty_tuple(self):
        result = rank_insights(())

        self.assertEqual(result, ())

    def test_single_insight_is_preserved(self):
        insight = self._insight(title="Only", priority=70)

        result = rank_insights((insight,))

        self.assertEqual(result, (insight,))

    def test_input_is_not_mutated(self):
        first = self._insight(title="First", priority=10)
        second = self._insight(title="Second", priority=90)
        original = [first, second]

        rank_insights(original)

        self.assertEqual(original, [first, second])

    def test_result_is_a_tuple(self):
        insight = self._insight(title="Test", priority=50)

        result = rank_insights([insight])

        self.assertIsInstance(result, tuple)

    def test_case_insensitive_title_ordering(self):
        lower = self._insight(title="alpha", priority=50)
        upper = self._insight(title="Beta", priority=50)

        result = rank_insights((lower, upper))

        self.assertEqual(
            [insight.title for insight in result],
            ["alpha", "Beta"],
        )

    def test_priority_is_primary_over_metric_presence(self):
        low_with_metric = self._insight(
            title="Low metric",
            priority=40,
            metric=Decimal("100"),
        )
        high_without_metric = self._insight(
            title="High no metric",
            priority=90,
            metric=None,
        )

        result = rank_insights((low_with_metric, high_without_metric))

        self.assertEqual(
            [insight.title for insight in result],
            ["High no metric", "Low metric"],
        )