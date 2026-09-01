from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from recommendations.models import OffsetProject
from recommendations.services.signals import RecommendationSignals


# ---------------------------------------------------------------------
# Offset requirement
# ---------------------------------------------------------------------

KG_PER_TONNE = Decimal("1000")


# ---------------------------------------------------------------------
# Project scoring weights
# Total = 100%
# ---------------------------------------------------------------------

DOMAIN_WEIGHT = Decimal("0.30")
GEOGRAPHY_WEIGHT = Decimal("0.25")
SDG_WEIGHT = Decimal("0.20")
PROJECT_TYPE_WEIGHT = Decimal("0.15")
QUALITY_WEIGHT = Decimal("0.10")


# ---------------------------------------------------------------------
# CarbonIQ category -> broad sustainability domain
# ---------------------------------------------------------------------

CATEGORY_DOMAIN_MAP: dict[str, str] = {
    "Electricity": "energy",
    "Transportation": "transport",
    "Petrol": "transport",
    "Diesel": "transport",

    "Rice & Grain": "food",
    "Legumes": "food",
    "Milk": "food",
    "Tofu": "food",
    "Fruit": "food",
    "Vegetables": "food",

    "Clothing": "shopping",
    "Footwear": "shopping",

    "Waste": "waste",
}


# ---------------------------------------------------------------------
# Offset project text -> broad sustainability domain
#
# This is only a controlled matching vocabulary for recommendation
# ranking. It does NOT modify the source registry classification.
# ---------------------------------------------------------------------

PROJECT_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "energy": (
        "renewable",
        "solar",
        "wind",
        "hydro",
        "hydroelectric",
        "biogas",
        "cookstove",
        "energy efficiency",
        "clean energy",
        "electricity",
    ),
    "nature": (
        "forest",
        "forestry",
        "afforestation",
        "reforestation",
        "agroforestry",
        "a/r",
        "land restoration",
        "restoration",
        "nature",
    ),
    "food": (
        "agriculture",
        "agricultural",
        "regenerative",
        "rice",
        "farmland",
        "farming",
        "livestock",
    ),
    "waste": (
        "waste",
        "landfill",
        "methane recovery",
        "methane",
        "biogas recovery",
    ),
    "transport": (
        "transport",
        "transportation",
        "mobility",
        "vehicle",
        "fuel",
    ),
    "shopping": (
        "material",
        "recycling",
        "circular",
        "textile",
    ),
}


@dataclass(frozen=True)
class OffsetRequirement:
    """
    Indicative offset requirement calculated from the user's
    latest completed monthly carbon footprint.

    This is a guidance value only. It is not a purchase quantity,
    retirement instruction, or claim of emissions cancellation.
    """

    latest_month_emission_kg: Decimal
    indicative_tonnes: Decimal
    source_month: Any
    source: str


@dataclass(frozen=True)
class OffsetProjectScore:
    """
    Complete scoring result for one offset project.
    """

    project: OffsetProject

    score: Decimal

    domain_score: Decimal
    geography_score: Decimal
    sdg_score: Decimal
    project_type_score: Decimal
    quality_score: Decimal

    applicable: bool


def _clamp(
    value: Decimal,
    minimum: Decimal = Decimal("0"),
    maximum: Decimal = Decimal("100"),
) -> Decimal:
    """
    Keep a Decimal value inside the supplied range.
    """

    if value < minimum:
        return minimum

    if value > maximum:
        return maximum

    return value


def calculate_offset_requirement(
    signals: RecommendationSignals,
) -> OffsetRequirement | None:
    """
    Calculate the user's indicative offset requirement.

    CarbonIQ uses the latest completed calendar month's emissions,
    not lifetime cumulative emissions.

    Example:

        840 kg CO2e
        / 1000
        = 0.8400 tonnes CO2e
    """

    if not signals.monthly_emissions:
        return None

    latest_row = max(
        signals.monthly_emissions,
        key=lambda row: row["month"],
    )

    latest_emission = Decimal(
        str(
            latest_row.get(
                "total_emission",
                Decimal("0"),
            )
        )
    )

    if latest_emission <= Decimal("0"):
        return None

    indicative_tonnes = (
        latest_emission / KG_PER_TONNE
    ).quantize(
        Decimal("0.0001")
    )

    return OffsetRequirement(
        latest_month_emission_kg=latest_emission,
        indicative_tonnes=indicative_tonnes,
        source_month=latest_row["month"],
        source="latest_completed_month",
    )


def _get_user_domain(
    signals: RecommendationSignals,
) -> str | None:
    """
    Determine the user's strongest sustainability domain.

    K-Means dominant_domain takes precedence when available.
    Otherwise the user's highest-emission category is used.
    """

    if signals.dominant_domain:
        return (
            str(signals.dominant_domain)
            .strip()
            .lower()
        )

    if signals.top_category:
        return CATEGORY_DOMAIN_MAP.get(
            signals.top_category
        )

    return None


def _get_project_domains(
    project: OffsetProject,
) -> set[str]:
    """
    Determine broad semantic domains for an offset project.

    The matching is based on source-provided project text and does
    not overwrite the project's original registry classification.
    """

    searchable_text = " ".join(
        (
            project.name or "",
            project.description or "",
            project.project_type or "",
        )
    ).lower()

    matched_domains: set[str] = set()

    for domain, keywords in PROJECT_DOMAIN_KEYWORDS.items():
        if any(
            keyword in searchable_text
            for keyword in keywords
        ):
            matched_domains.add(domain)

    return matched_domains


def calculate_domain_score(
    project: OffsetProject,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Score project alignment with the user's dominant domain.

    Scoring:
        100 -> exact domain match
         25 -> project has a known but different domain
         50 -> insufficient information
    """

    user_domain = _get_user_domain(
        signals
    )

    project_domains = _get_project_domains(
        project
    )

    if user_domain is None:
        return Decimal("50")

    if not project_domains:
        return Decimal("50")

    if user_domain in project_domains:
        return Decimal("100")

    return Decimal("25")


def _get_user_country(
    user,
) -> str:
    """
    CarbonIQ currently operates with Indian user geography.

    UserLocation stores state and district for benchmarking, while
    the current Gold Standard export provides project country but not
    project region/state.

    Therefore country-level geography is the reliable common signal.
    """

    # Keep this function separate so the geography policy can later
    # evolve without changing the rest of the scoring engine.

    return "india"


def calculate_geography_score(
    project: OffsetProject,
    user,
) -> Decimal:
    """
    Score country-level geographic relevance.

    Current project data:
        - user geography: India
        - registry project geography: country

    Scoring:
        100 -> India project for an India CarbonIQ user
         40 -> project outside India
         50 -> project country unavailable
    """

    project_country = (
        project.country or ""
    ).strip().lower()

    if not project_country:
        return Decimal("50")

    user_country = _get_user_country(
        user
    )

    if project_country == user_country:
        return Decimal("100")

    return Decimal("40")


def calculate_sdg_score(
    project: OffsetProject,
) -> Decimal:
    """
    Score SDG alignment.

    SDG 13 (Climate Action) receives the strongest score because
    CarbonIQ is a climate-action platform.

    Scoring:
        100 -> SDG 13 explicitly present
         60 -> other SDG information available
         40 -> no SDG information available
    """

    sdg_numbers: set[int] = set()

    for item in project.sdg_impacts or []:
        if not isinstance(item, dict):
            continue

        value = item.get("sdg")

        try:
            sdg_number = int(value)
        except (TypeError, ValueError):
            continue

        if 1 <= sdg_number <= 17:
            sdg_numbers.add(
                sdg_number
            )

    if 13 in sdg_numbers:
        return Decimal("100")

    if sdg_numbers:
        return Decimal("60")

    return Decimal("40")


def calculate_project_type_score(
    project: OffsetProject,
) -> Decimal:
    """
    Score project-type metadata availability.

    This measures classification usefulness, not environmental
    quality or certification quality.
    """

    project_type = (
        project.project_type or ""
    ).strip()

    if not project_type:
        return Decimal("50")

    return Decimal("100")


def calculate_quality_score(
    project: OffsetProject,
) -> Decimal:
    """
    Score completeness of source metadata.

    This is metadata completeness only. It must not be interpreted
    as a scientific or financial quality rating of the project.
    """

    fields_present = (
        bool(project.name),
        bool(project.registry),
        bool(project.registry_project_id),
        bool(project.registry_url),
        bool(project.country),
        bool(project.project_type),
        bool(project.source_last_verified_at),
    )

    completed_fields = sum(
        1
        for field_present in fields_present
        if field_present
    )

    return (
        Decimal(completed_fields)
        / Decimal(len(fields_present))
        * Decimal("100")
    ).quantize(
        Decimal("0.0001")
    )


def is_offset_project_applicable(
    project: OffsetProject,
) -> bool:
    """
    Determine whether a project may be recommended.

    CarbonIQ requires both:
        - local project record is active
        - normalized registry status is ACTIVE
    """

    return (
        project.is_active
        and project.status
        == OffsetProject.ProjectStatus.ACTIVE
    )


def calculate_offset_project_score(
    project: OffsetProject,
    signals: RecommendationSignals,
    user,
) -> OffsetProjectScore:
    """
    Calculate the complete personalized score for one project.
    """

    applicable = is_offset_project_applicable(
        project
    )

    domain_score = calculate_domain_score(
        project,
        signals,
    )

    geography_score = calculate_geography_score(
        project,
        user,
    )

    sdg_score = calculate_sdg_score(
        project
    )

    project_type_score = (
        calculate_project_type_score(
            project
        )
    )

    quality_score = calculate_quality_score(
        project
    )

    weighted_score = (
        domain_score * DOMAIN_WEIGHT
        + geography_score * GEOGRAPHY_WEIGHT
        + sdg_score * SDG_WEIGHT
        + project_type_score * PROJECT_TYPE_WEIGHT
        + quality_score * QUALITY_WEIGHT
    )

    weighted_score = _clamp(
        weighted_score
    ).quantize(
        Decimal("0.0001")
    )

    if not applicable:
        weighted_score = Decimal("0.0000")

    return OffsetProjectScore(
        project=project,
        score=weighted_score,
        domain_score=domain_score,
        geography_score=geography_score,
        sdg_score=sdg_score,
        project_type_score=project_type_score,
        quality_score=quality_score,
        applicable=applicable,
    )


def rank_offset_projects(
    projects: list[OffsetProject],
    signals: RecommendationSignals,
    user,
) -> list[OffsetProjectScore]:
    """
    Score and rank offset projects deterministically.

    Non-applicable projects remain in the returned result with a
    score of zero. The recommendation-generation service can filter
    them before persistence.
    """

    scored_projects = [
        calculate_offset_project_score(
            project=project,
            signals=signals,
            user=user,
        )
        for project in projects
    ]

    return sorted(
        scored_projects,
        key=lambda result: (
            -result.score,
            -result.domain_score,
            -result.geography_score,
            -result.sdg_score,
            result.project.name.lower(),
        ),
    )