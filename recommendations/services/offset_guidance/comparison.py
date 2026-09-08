from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from recommendations.models import OffsetRecommendation

from .suitability import build_offset_suitability
from .verification import build_offset_verification


@dataclass(frozen=True)
class OffsetProjectComparison:
    """
    Read-only comparison representation for one persisted
    OffsetRecommendation.

    The stored recommendation score is preserved exactly as the
    E5 generated score. E9 does not recompute historical scoring
    components.
    """

    rank: int
    recommendation_id: int
    project_name: str
    score: Decimal
    registry: str
    registry_project_id: str
    project_type: str
    country: str
    region: str
    project_status: str
    project_status_label: str
    verification_state: str
    verification_state_label: str
    days_since_verification: int
    sdg_13_aligned: bool
    suitability_match_count: int
    registry_url: str
    certification_documents_url: str


def _contains_sdg_13(project) -> bool:
    """
    Return True only when SDG 13 is explicitly present in the
    source-provided SDG metadata.
    """

    for item in project.sdg_impacts or []:
        if not isinstance(item, dict):
            continue

        try:
            if int(item.get("sdg")) == 13:
                return True
        except (TypeError, ValueError):
            continue

    return False


def build_project_comparison(
    recommendations: Iterable[OffsetRecommendation],
) -> tuple[OffsetProjectComparison, ...]:
    """
    Build a deterministic comparison view for persisted offset
    recommendations.

    The caller is responsible for supplying recommendations that
    belong to the same user.

    Ordering is based on the persisted E5 recommendation score,
    followed by project name for deterministic tie-breaking.
    """

    ordered = sorted(
        recommendations,
        key=lambda recommendation: (
            -recommendation.score,
            recommendation.offset_project.name.casefold(),
            -recommendation.generated_at.timestamp(),
        ),
    )

    comparisons: list[OffsetProjectComparison] = []

    for rank, recommendation in enumerate(
        ordered,
        start=1,
    ):
        project = recommendation.offset_project

        verification = build_offset_verification(
            project,
        )

        suitability = build_offset_suitability(
            project,
            score=recommendation.score,
        )

        comparisons.append(
            OffsetProjectComparison(
                rank=rank,
                recommendation_id=recommendation.id,
                project_name=project.name,
                score=recommendation.score,
                registry=project.registry,
                registry_project_id=(
                    project.registry_project_id
                ),
                project_type=project.project_type,
                country=project.country,
                region=project.region,
                project_status=project.status,
                project_status_label=(
                    verification.status_label
                ),
                verification_state=(
                    verification.state
                ),
                verification_state_label=(
                    verification.state_label
                ),
                days_since_verification=(
                    verification.days_since_verification
                ),
                sdg_13_aligned=_contains_sdg_13(
                    project
                ),
                suitability_match_count=(
                    suitability.matched_factor_count
                ),
                registry_url=project.registry_url,
                certification_documents_url=(
                    project.certification_documents_url
                ),
            )
        )

    return tuple(comparisons)