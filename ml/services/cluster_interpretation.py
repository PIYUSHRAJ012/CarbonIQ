from __future__ import annotations

from dataclasses import dataclass
from math import isfinite
from typing import Mapping


DEFAULT_DOMAINS = (
    "energy",
    "transport",
    "food",
    "shopping",
    "waste",
)

DOMINANCE_THRESHOLD = 1.25


class ClusterInterpretationError(Exception):
    """
    Raised when a K-Means cluster cannot be interpreted safely.
    """


@dataclass(frozen=True)
class ClusterProfile:
    """
    Human-readable interpretation of a K-Means cluster.
    """

    cluster_id: int
    profile_name: str
    dominant_domain: str
    domain_scores: dict[str, float]
    feature_strengths: dict[str, float]


_FEATURE_DOMAIN_MAP = {
    # Energy
    "electricity": "energy",

    # Transportation
    "transportation": "transport",
    "petrol": "transport",
    "diesel": "transport",

    # Food
    "food": "food",
    "rice_grain": "food",
    "legumes": "food",
    "milk": "food",
    "tofu": "food",
    "fruit": "food",
    "vegetables": "food",

    # Shopping
    "shopping": "shopping",
    "clothing": "shopping",
    "footwear": "shopping",

    # Waste
    "waste": "waste",
}


def map_feature_to_domain(
    feature_name: str,
) -> str | None:
    """
    Map a canonical ML feature name to a behavioural domain.

    Features that are not behavioural categories, such as summary
    statistics, return None.
    """

    if not isinstance(feature_name, str):
        return None

    return _FEATURE_DOMAIN_MAP.get(
        feature_name
    )


def _validate_numeric_mapping(
    values: Mapping[str, float],
    mapping_name: str,
) -> None:
    """
    Validate that all values in a mapping are finite numbers.
    """

    for feature_name, value in values.items():
        if not isinstance(
            value,
            (int, float),
        ):
            raise ClusterInterpretationError(
                f"{mapping_name} contains a non-numeric value "
                f"for feature '{feature_name}'."
            )

        if not isfinite(float(value)):
            raise ClusterInterpretationError(
                f"{mapping_name} contains a non-finite value "
                f"for feature '{feature_name}'."
            )


def calculate_domain_scores(
    centroid: Mapping[str, float],
    population_means: Mapping[str, float],
) -> dict[str, float]:
    """
    Calculate relative domain strengths.

    For each mapped behavioural feature:

        feature strength =
            cluster centroid / population mean

    Multiple features belonging to the same domain are averaged.
    Unknown or non-behavioural features are ignored.
    """

    _validate_numeric_mapping(
        centroid,
        "Centroid",
    )

    _validate_numeric_mapping(
        population_means,
        "Population means",
    )

    domain_values: dict[str, list[float]] = {
        domain: []
        for domain in DEFAULT_DOMAINS
    }

    for feature_name, centroid_value in centroid.items():
        domain = map_feature_to_domain(
            feature_name
        )

        if domain is None:
            continue

        if feature_name not in population_means:
            raise ClusterInterpretationError(
                "Population means are missing feature "
                f"'{feature_name}'."
            )

        population_mean = float(
            population_means[feature_name]
        )

        if population_mean == 0:
            relative_strength = 0.0
        else:
            relative_strength = (
                float(centroid_value)
                / population_mean
            )

        domain_values[domain].append(
            relative_strength
        )

    return {
        domain: (
            sum(values) / len(values)
            if values
            else 0.0
        )
        for domain, values in domain_values.items()
    }


def _calculate_feature_strengths(
    centroid: Mapping[str, float],
    population_means: Mapping[str, float],
) -> dict[str, float]:
    """
    Calculate relative strength for each mapped behavioural feature.
    """

    strengths: dict[str, float] = {}

    for feature_name, centroid_value in centroid.items():
        domain = map_feature_to_domain(
            feature_name
        )

        if domain is None:
            continue

        if feature_name not in population_means:
            raise ClusterInterpretationError(
                "Population means are missing feature "
                f"'{feature_name}'."
            )

        population_mean = float(
            population_means[feature_name]
        )

        if population_mean == 0:
            strengths[feature_name] = 0.0
        else:
            strengths[feature_name] = (
                float(centroid_value)
                / population_mean
            )

    return strengths


def _determine_profile(
    domain_scores: Mapping[str, float],
) -> tuple[str, str]:
    """
    Determine the dominant behavioural profile.

    A domain must be sufficiently stronger than the second-highest
    domain to receive a specialised profile. Otherwise the cluster
    is described as balanced.
    """

    ranked_domains = sorted(
        domain_scores.items(),
        key=lambda item: item[1],
        reverse=True,
    )

    if not ranked_domains:
        return (
            "balanced",
            "Balanced profile",
        )

    dominant_domain, dominant_score = (
        ranked_domains[0]
    )

    second_score = (
        ranked_domains[1][1]
        if len(ranked_domains) > 1
        else 0.0
    )

    if dominant_score <= 0:
        return (
            "balanced",
            "Balanced profile",
        )

    if second_score <= 0:
        dominance_ratio = float("inf")
    else:
        dominance_ratio = (
            dominant_score / second_score
        )

    if dominance_ratio < DOMINANCE_THRESHOLD:
        return (
            "balanced",
            "Balanced profile",
        )

    profile_names = {
        "energy": "Energy-oriented",
        "transport": "Transport-oriented",
        "food": "Food-oriented",
        "shopping": "Shopping-oriented",
        "waste": "Waste-oriented",
    }

    return (
        dominant_domain,
        profile_names.get(
            dominant_domain,
            "Balanced profile",
        ),
    )


def interpret_cluster(
    cluster_id: int,
    centroid: Mapping[str, float],
    population_means: Mapping[str, float],
) -> ClusterProfile:
    """
    Generate a human-readable profile for one K-Means cluster.

    The interpretation is determined from cluster characteristics,
    not from the numerical cluster ID.
    """

    if not isinstance(
        cluster_id,
        int,
    ):
        raise ClusterInterpretationError(
            "cluster_id must be an integer."
        )

    if not centroid:
        raise ClusterInterpretationError(
            "Cluster centroid cannot be empty."
        )

    if not population_means:
        raise ClusterInterpretationError(
            "Population means cannot be empty."
        )

    domain_scores = calculate_domain_scores(
        centroid,
        population_means,
    )

    feature_strengths = (
        _calculate_feature_strengths(
            centroid,
            population_means,
        )
    )

    dominant_domain, profile_name = (
        _determine_profile(
            domain_scores
        )
    )

    return ClusterProfile(
        cluster_id=cluster_id,
        profile_name=profile_name,
        dominant_domain=dominant_domain,
        domain_scores={
            domain: float(score)
            for domain, score in domain_scores.items()
        },
        feature_strengths={
            feature: float(strength)
            for feature, strength in feature_strengths.items()
        },
    )