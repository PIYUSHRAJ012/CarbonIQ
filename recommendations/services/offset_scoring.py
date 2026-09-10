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

DOMAIN_WEIGHT = Decimal("0.40")
GEOGRAPHY_WEIGHT = Decimal("0.15")
SDG_WEIGHT = Decimal("0.15")
PROJECT_TYPE_WEIGHT = Decimal("0.20")
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

# ---------------------------------------------------------------------
# Explicit Gold Standard project-type -> sustainability domains
#
# These mappings are used only for recommendation ranking.
# They do not alter the source registry classification.
# ---------------------------------------------------------------------

PROJECT_TYPE_DOMAIN_KEYWORDS: dict[str, tuple[str, ...]] = {
    "energy": (
        "energy efficiency - domestic",
        "energy efficiency - industrial",
        "energy efficiency - commercial sector",
        "energy efficiency - public sector",
        "wind",
        "solar thermal - electricity",
        "solar thermal - heat",
        "small, low - impact hydro",
        "pv",
        "geothermal",
        "biogas - heat",
        "biogas - electricity",
        "biogas - cogeneration",
        "biomass, or liquid biofuel - heat",
        "biomass, or liquid biofuel - electricity",
        "biomass, or liquid biofuel - cogeneration",
    ),
    "transport": (
        "energy efficiency - transport sector",
    ),
    "food": (
        "energy efficiency - agriculture sector",
    ),
    "nature": (
        "a/r",
    ),
    "waste": (
        "biogas - heat",
        "biogas - electricity",
        "biogas - cogeneration",
    ),
}

# ---------------------------------------------------------------------
# CarbonIQ category -> specific Gold Standard project types
#
# This mapping provides finer-grained personalization than the broad
# sustainability-domain mapping.
#
# Only project types actually present in the imported Gold Standard
# registry dataset are included.
# ---------------------------------------------------------------------

CATEGORY_PROJECT_TYPE_RELEVANCE: dict[str, tuple[str, ...]] = {
    "Electricity": (
        "PV",
        "Solar Thermal - Electricity",
        "Wind",
        "Small, Low - Impact Hydro",
        "Geothermal",
        "Biogas - Electricity",
        "Biomass, or Liquid Biofuel - Electricity",
    ),
    "Transportation": (
        "Energy Efficiency - Transport Sector",
    ),
    "Petrol": (
        "Energy Efficiency - Transport Sector",
    ),
    "Diesel": (
        "Energy Efficiency - Transport Sector",
    ),
    "Rice & Grain": (
        "Energy Efficiency - Agriculture Sector",
    ),
    "Legumes": (
        "Energy Efficiency - Agriculture Sector",
    ),
    "Milk": (
        "Energy Efficiency - Agriculture Sector",
    ),
    "Tofu": (
        "Energy Efficiency - Agriculture Sector",
    ),
    "Fruit": (
        "Energy Efficiency - Agriculture Sector",
    ),
    "Vegetables": (
        "Energy Efficiency - Agriculture Sector",
    ),
    "Waste": (
        "Biogas - Heat",
        "Biogas - Electricity",
        "Biogas - Cogeneration",
        "Biomass, or Liquid Biofuel - Heat",
        "Biomass, or Liquid Biofuel - Electricity",
        "Biomass, or Liquid Biofuel - Cogeneration",
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


def _normalise_text(
    value: str | None,
) -> str:
    """
    Normalize text for deterministic matching.
    """
    if not value:
        return ""

    return " ".join(
        str(value).strip().casefold().split()
    )


def _get_project_type_domains(
    project: OffsetProject,
) -> set[str]:
    """
    Determine sustainability domains from the explicit
    Gold Standard project type.

    Explicit registry classification is treated as stronger
    evidence than free-text description matching.
    """

    project_type = _normalise_text(
        project.project_type
    )

    if not project_type:
        return set()

    matched_domains: set[str] = set()

    for domain, project_types in (
        PROJECT_TYPE_DOMAIN_KEYWORDS.items()
    ):
        if any(
            project_type == candidate
            or candidate in project_type
            for candidate in project_types
        ):
            matched_domains.add(domain)

    return matched_domains


def _get_project_text_domains(
    project: OffsetProject,
) -> set[str]:
    """
    Determine supporting sustainability domains from project text.

    Free-text matching is secondary to explicit project-type
    classification.
    """

    searchable_text = " ".join(
        (
            project.name or "",
            project.description or "",
            project.project_type or "",
        )
    ).casefold()

    matched_domains: set[str] = set()

    for domain, keywords in PROJECT_DOMAIN_KEYWORDS.items():
        if any(
            keyword.casefold() in searchable_text
            for keyword in keywords
        ):
            matched_domains.add(domain)

    return matched_domains


def _get_project_domains(
    project: OffsetProject,
) -> set[str]:
    """
    Determine broad sustainability domains for an offset project.

    Explicit registry project type is preferred. Free-text
    matching is used only when project-type classification
    is unavailable.
    """

    explicit_domains = _get_project_type_domains(
        project
    )

    if explicit_domains:
        return explicit_domains

    return _get_project_text_domains(
        project
    )


def _count_domain_supporting_keywords(
    project: OffsetProject,
    user_domain: str,
) -> int:
    """
    Count distinct source-text keywords supporting the user's
    dominant sustainability domain.
    """

    searchable_text = " ".join(
        (
            project.name or "",
            project.description or "",
            project.project_type or "",
        )
    ).casefold()

    keywords = PROJECT_DOMAIN_KEYWORDS.get(
        user_domain,
        (),
    )

    return sum(
        1
        for keyword in keywords
        if keyword.casefold() in searchable_text
    )


def calculate_domain_score(
    project: OffsetProject,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Score project alignment with the user's dominant domain.

    Scoring:
        100 -> explicit project-type match with strong supporting evidence
         80 -> explicit project-type match
         60-75 -> text-only domain match
         25 -> known but different domain
         50 -> insufficient information
    """

    user_domain = _get_user_domain(
        signals
    )

    if user_domain is None:
        return Decimal("50")

    explicit_domains = _get_project_type_domains(
        project
    )

    text_domains = _get_project_text_domains(
        project
    )

    # Strongest evidence: explicit registry classification.
    if user_domain in explicit_domains:
        supporting_keywords = min(
            _count_domain_supporting_keywords(
                project,
                user_domain,
            ),
            4,
        )

        return (
            Decimal("80")
            + Decimal(supporting_keywords)
            * Decimal("5")
        )

    # Secondary evidence: project text only.
    if user_domain in text_domains:
        supporting_keywords = min(
            _count_domain_supporting_keywords(
                project,
                user_domain,
            ),
            3,
        )

        return (
            Decimal("60")
            + Decimal(supporting_keywords)
            * Decimal("5")
        )

    # A known sustainability domain exists, but it does not
    # match the user's dominant domain.
    if explicit_domains or text_domains:
        return Decimal("25")

    return Decimal("50")


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

def _score_project_type_for_category(
    project: OffsetProject,
    category: str,
) -> Decimal:
    """
    Score a project type against one user's emission category.

    Scoring:
        100 -> direct project-type match
         70 -> broader sustainability-domain match
         25 -> known but unrelated project type
         50 -> insufficient information
    """

    project_type = _normalise_text(
        project.project_type
    )

    if not project_type or project_type == "other":
        return Decimal("50")

    specific_project_types = {
        _normalise_text(value)
        for value in CATEGORY_PROJECT_TYPE_RELEVANCE.get(
            category,
            (),
        )
    }

    if project_type in specific_project_types:
        return Decimal("100")

    category_domain = CATEGORY_DOMAIN_MAP.get(
        category
    )

    if category_domain is None:
        return Decimal("50")

    project_domains = _get_project_type_domains(
        project
    )

    if not project_domains:
        return Decimal("50")

    if category_domain in project_domains:
        return Decimal("70")

    return Decimal("25")


def calculate_project_type_score(
    project: OffsetProject,
    signals: RecommendationSignals,
) -> Decimal:
    """
    Score project-type alignment against the user's complete
    emission-category distribution.

    Each category contributes according to its share of the
    user's total categorized emissions.

    This avoids treating the user as belonging exclusively to
    the single highest-emission category.
    """

    category_emissions = signals.category_emissions

    if not category_emissions:
        if signals.top_category:
            return _score_project_type_for_category(
                project,
                signals.top_category,
            )

        return Decimal("50")

    positive_categories = []

    for row in category_emissions:
        category = row.get("category__name")
        emission = Decimal(
            str(
                row.get(
                    "total_emission",
                    Decimal("0"),
                )
            )
        )

        if (
            category
            and emission > Decimal("0")
        ):
            positive_categories.append(
                (str(category), emission)
            )

    if not positive_categories:
        return Decimal("50")

    total_emission = sum(
        emission
        for _, emission in positive_categories
    )

    if total_emission <= Decimal("0"):
        return Decimal("50")

    weighted_score = sum(
        (
            _score_project_type_for_category(
                project,
                category,
            )
            * emission
        )
        for category, emission in positive_categories
    ) / total_emission

    return _clamp(
        weighted_score
    ).quantize(
        Decimal("0.0001")
    )

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
            project,
            signals,
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