from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Iterable

from recommendations.models import OffsetProject


@dataclass(frozen=True)
class SuitabilityFactor:
    """
    One explainable factor contributing to project suitability.

    The factor describes an existing property of the recommendation.
    It does not create or alter the underlying E5 score.
    """

    key: str
    label: str
    matched: bool
    explanation: str


@dataclass(frozen=True)
class OffsetSuitability:
    """
    Explainable suitability information for an offset project.
    """

    project_name: str
    score: Decimal | None
    factors: tuple[SuitabilityFactor, ...]
    matched_factor_count: int

    @property
    def summary(self) -> str:
        if self.matched_factor_count == 0:
            return (
                "This project has no additional suitability "
                "matches identified from the available user and "
                "project information."
            )

        if self.matched_factor_count == 1:
            return (
                "This project has 1 suitability match based on "
                "the available information."
            )

        return (
            f"This project has {self.matched_factor_count} "
            "suitability matches based on the available information."
        )


def _normalise(value: str | None) -> str:
    if not value:
        return ""

    return value.strip().casefold()


def _project_country(project: OffsetProject) -> str:
    return _normalise(project.country)


def _project_type(project: OffsetProject) -> str:
    return _normalise(project.project_type)


def _project_sdg_numbers(project: OffsetProject) -> set[int]:
    """
    Extract SDG numbers from the stored project metadata.

    CarbonIQ only uses explicitly stored SDG metadata.
    Missing or malformed entries are ignored rather than guessed.
    """

    sdgs = project.sdg_impacts or []

    result: set[int] = set()

    for item in sdgs:
        if not isinstance(item, dict):
            continue

        value = item.get("sdg")

        try:
            result.add(int(value))
        except (TypeError, ValueError):
            continue

    return result


def build_suitability_factors(
    project: OffsetProject,
    *,
    user_country: str = "India",
    preferred_project_types: Iterable[str] | None = None,
) -> tuple[SuitabilityFactor, ...]:
    """
    Build explainable suitability factors.

    The function uses only:
      - project metadata already stored in OffsetProject
      - explicit user context passed by the caller

    It does not infer a user's preferences.
    """

    factors: list[SuitabilityFactor] = []

    project_country = _project_country(project)
    normalized_user_country = _normalise(user_country)

    country_match = (
        bool(project_country)
        and bool(normalized_user_country)
        and project_country == normalized_user_country
    )

    factors.append(
        SuitabilityFactor(
            key="country_match",
            label="Geographic alignment",
            matched=country_match,
            explanation=(
                "The project is located in India."
                if country_match
                else (
                    "The project location does not match the "
                    "configured user country."
                )
            ),
        )
    )

    sdgs = _project_sdg_numbers(project)

    climate_action_match = 13 in sdgs

    factors.append(
        SuitabilityFactor(
            key="sdg_13",
            label="Climate Action alignment",
            matched=climate_action_match,
            explanation=(
                "The project explicitly lists SDG 13 "
                "(Climate Action)."
                if climate_action_match
                else (
                    "SDG 13 is not explicitly listed in the "
                    "available project metadata."
                )
            ),
        )
    )

    project_type = _project_type(project)

    has_project_type = bool(project_type)

    factors.append(
        SuitabilityFactor(
            key="project_type_available",
            label="Project-type information",
            matched=has_project_type,
            explanation=(
                f"Project type is identified as "
                f"{project.project_type}."
                if has_project_type
                else (
                    "Project-type information is unavailable "
                    "in the stored registry metadata."
                )
            ),
        )
    )

    if preferred_project_types is not None:
        normalized_preferences = {
            _normalise(value)
            for value in preferred_project_types
            if value
        }

        project_type_match = (
            bool(project_type)
            and project_type in normalized_preferences
        )

        factors.append(
            SuitabilityFactor(
                key="preferred_project_type",
                label="Preferred project type",
                matched=project_type_match,
                explanation=(
                    "The project type matches an explicitly "
                    "configured user preference."
                    if project_type_match
                    else (
                        "The project type does not match any "
                        "explicitly configured user preference."
                    )
                ),
            )
        )

    return tuple(factors)


def build_offset_suitability(
    project: OffsetProject,
    *,
    score: Decimal | None = None,
    user_country: str = "India",
    preferred_project_types: Iterable[str] | None = None,
) -> OffsetSuitability:
    """
    Build explainable suitability information for a project.

    `score` is passed through from the existing E5 recommendation.
    This function never recalculates or modifies that score.
    """

    factors = build_suitability_factors(
        project,
        user_country=user_country,
        preferred_project_types=preferred_project_types,
    )

    matched_factor_count = sum(
        1
        for factor in factors
        if factor.matched
    )

    return OffsetSuitability(
        project_name=project.name,
        score=score,
        factors=factors,
        matched_factor_count=matched_factor_count,
    )