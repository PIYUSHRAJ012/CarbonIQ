from __future__ import annotations

import logging

from .engine import (
    RecommendationEngineError,
    generate_user_recommendations,
)
from .offset_recommendations import (
    OffsetRecommendationError,
    generate_offset_recommendations,
)


logger = logging.getLogger(__name__)


def refresh_user_recommendations(user) -> bool:
    """
    Refresh personalized CarbonIQ recommendations for a user.

    This downstream operation includes:
        1. Generic sustainability/action recommendations.
        2. Registry-backed offset project recommendations.

    Recommendation failures must never cause an otherwise successful
    carbon submission to fail.

    Returns:
        True  -> all recommendation generation steps succeeded.
        False -> one or more recommendation generation steps failed.
    """

    success = True

    try:
        generate_user_recommendations(user)

    except RecommendationEngineError:
        success = False

        logger.exception(
            "Sustainability recommendation generation failed "
            "for user_id=%s.",
            user.id,
        )

    except Exception:
        success = False

        logger.exception(
            "Unexpected sustainability recommendation integration "
            "error for user_id=%s.",
            user.id,
        )

    try:
        generate_offset_recommendations(user)

    except OffsetRecommendationError:
        success = False

        logger.exception(
            "Offset recommendation generation failed "
            "for user_id=%s.",
            user.id,
        )

    except Exception:
        success = False

        logger.exception(
            "Unexpected offset recommendation integration "
            "error for user_id=%s.",
            user.id,
        )

    return success