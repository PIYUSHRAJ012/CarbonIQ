from __future__ import annotations

from .contracts import Insight
from .signals import InsightSignals
from .generator import generate_insights
from .ranker import rank_insights


def build_insights(signals: InsightSignals) -> tuple[Insight, ...]:
    """
    Generate insights from the supplied signals and return them
    in deterministic ranked order.
    """
    generated = generate_insights(signals)
    return rank_insights(generated)