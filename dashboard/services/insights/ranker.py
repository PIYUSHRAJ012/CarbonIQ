from __future__ import annotations

from collections.abc import Iterable

from .contracts import Insight


def _sort_key(insight: Insight) -> tuple[int, int, str, str]:
    """
    Deterministic ranking key.

    Higher priority comes first.
    For equal priorities, longer metric evidence comes first when present.
    Finally, title/message provide stable deterministic ordering.
    """
    metric_present = 1 if insight.metric is not None else 0

    return (
        -insight.priority,
        -metric_present,
        insight.title.lower(),
        insight.message.lower(),
    )


def rank_insights(insights: Iterable[Insight]) -> tuple[Insight, ...]:
    """
    Return insights in deterministic priority order.

    The function does not mutate the input collection and does not
    generate or modify insight content.
    """
    return tuple(sorted(insights, key=_sort_key))