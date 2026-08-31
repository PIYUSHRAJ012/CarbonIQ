from __future__ import annotations

import logging

from .engine import (
    RecommendationEngineError,
    generate_user_recommendations,
)


logger = logging.getLogger(__name__)


def refresh_user_recommendations(user) -> bool:
    """
    Refresh personalized recommendations for a user.

    Recommendation generation is a downstream enhancement of the
    core CarbonIQ carbon-calculation workflow. A recommendation failure
    must therefore never cause an otherwise successful carbon
    submission to fail.

    Returns:
        True  -> recommendation generation succeeded
        False -> recommendation generation failed
    """

    try:
        generate_user_recommendations(user)
        return True

    except RecommendationEngineError:
        logger.exception(
            "Recommendation generation failed for user_id=%s.",
            user.id,
        )
        return False

    except Exception:
        logger.exception(
            "Unexpected recommendation integration error "
            "for user_id=%s.",
            user.id,
        )
        return False