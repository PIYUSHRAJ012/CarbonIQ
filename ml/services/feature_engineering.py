from __future__ import annotations

import re
from collections import defaultdict

import pandas as pd
from django.db.models import Prefetch

from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
)

class MLDataError(Exception):
    """
    Raised when CarbonIQ does not contain enough valid data
    to construct an ML dataset.
    """


def normalize_feature_name(category_name: str) -> str:
    """
    Convert a human-readable activity category into a stable
    ML feature name.

    Examples:
        "Electricity" -> "electricity"
        "Rice & Grain" -> "rice_grain"
        "Footwear" -> "footwear"
    """

    normalized = category_name.strip().lower()
    normalized = re.sub(r"[^a-z0-9]+", "_", normalized)
    normalized = normalized.strip("_")

    if not normalized:
        raise MLDataError(
            f"Activity category '{category_name}' cannot be converted "
            "into a valid feature name."
        )

    return normalized


def get_completed_activities():
    """
    Return completed carbon activities with the related data required
    for ML feature generation.

    Failed, pending, and processing submissions are excluded.
    """

    return (
        CarbonActivity.objects
        .filter(
            status=CarbonActivity.Status.COMPLETED,
            carbon_footprint__isnull=False,
        )
        .select_related(
            "user",
            "carbon_footprint",
        )
        .prefetch_related(
            Prefetch(
                "entries",
                queryset=ActivityEntry.objects.select_related("category"),
            )
        )
        .order_by("id")
    )


def get_prediction_dataset():
    """
    Build the Random Forest submission-level dataset.

    The feature schema is derived from all active ActivityCategory
    records so that every submission has the same feature columns.

    Returns:
        X: pandas.DataFrame
            Activity quantity features.

        y: pandas.Series
            Target total carbon emission.

        metadata: pandas.DataFrame
            Identifiers and timestamps useful for tracing records.
    """

    activities = list(get_completed_activities())

    if not activities:
        raise MLDataError(
            "No completed carbon activities with calculated footprints "
            "are available for ML training."
        )

    # Build the canonical feature schema from active categories.
    active_categories = (
        ActivityCategory.objects
        .filter(is_active=True)
        .order_by("display_order", "name")
    )

    feature_name_map = {}

    for category in active_categories:
        feature_name = normalize_feature_name(category.name)

        if feature_name in feature_name_map.values():
            raise MLDataError(
                f"Activity categories produce duplicate ML feature name: "
                f"'{feature_name}'."
            )

        feature_name_map[category.id] = feature_name

    if not feature_name_map:
        raise MLDataError(
            "No active activity categories are available "
            "for ML feature generation."
        )

    canonical_feature_names = sorted(feature_name_map.values())

    rows = []
    metadata_rows = []

    for activity in activities:
        feature_values = {
            feature_name: 0.0
            for feature_name in canonical_feature_names
        }

        for entry in activity.entries.all():
            feature_name = feature_name_map.get(entry.category_id)

            # Ignore entries belonging to inactive categories.
            if feature_name is None:
                continue

            feature_values[feature_name] += float(entry.quantity)

        rows.append(feature_values)

        metadata_rows.append(
            {
                "activity_id": activity.id,
                "user_id": activity.user_id,
                "created_at": activity.created_at,
                "calculated_at": activity.carbon_footprint.calculated_at,
            }
        )

    X = pd.DataFrame(
        rows,
        columns=canonical_feature_names,
    )

    if X.empty:
        raise MLDataError(
            "Completed activities contain no usable activity-entry data."
        )

    y = pd.Series(
        [
            float(activity.carbon_footprint.total_emission)
            for activity in activities
        ],
        name="total_emission",
    )

    metadata = pd.DataFrame(metadata_rows)

    return X, y, metadata

def get_temporal_prediction_dataset():
    """
    Build the temporal Random Forest prediction dataset.

    Each training row represents one user transitioning from one
    calendar month to the immediately following calendar month.

    Features are derived exclusively from the previous month.

    Target:
        next month's total carbon emission.

    Returns:
        X: pandas.DataFrame
            Previous-month activity and behavioural features.

        y: pandas.Series
            Next-month total carbon emission.

        metadata: pandas.DataFrame
            User and period information for each training row.
    """

    activities = list(get_completed_activities())

    if not activities:
        raise MLDataError(
            "No completed carbon activities with calculated footprints "
            "are available for temporal prediction training."
        )

    # ------------------------------------------------------------------
    # Build canonical feature schema from active activity categories.
    # ------------------------------------------------------------------
    active_categories = (
        ActivityCategory.objects
        .filter(is_active=True)
        .order_by("display_order", "name")
    )

    feature_name_map = {}

    for category in active_categories:
        feature_name = normalize_feature_name(category.name)

        if feature_name in feature_name_map.values():
            raise MLDataError(
                "Activity categories produce duplicate ML feature name: "
                f"'{feature_name}'."
            )

        feature_name_map[category.id] = feature_name

    if not feature_name_map:
        raise MLDataError(
            "No active activity categories are available "
            "for temporal ML feature generation."
        )

    canonical_feature_names = sorted(
        feature_name_map.values()
    )

    # ------------------------------------------------------------------
    # Build monthly profiles:
    #
    # user_id
    #     ↓
    # calendar month
    #     ↓
    # aggregate activity quantities and emissions
    # ------------------------------------------------------------------
    monthly_profiles = defaultdict(dict)

    for activity in activities:
        period = activity.created_at.date().replace(day=1)
        user_id = activity.user_id

        if period not in monthly_profiles[user_id]:
            monthly_profiles[user_id][period] = {
                "feature_totals": {
                    feature_name: 0.0
                    for feature_name in canonical_feature_names
                },
                "total_emission": 0.0,
                "submission_count": 0,
            }

        profile = monthly_profiles[user_id][period]

        for entry in activity.entries.all():
            feature_name = feature_name_map.get(
                entry.category_id
            )

            # Ignore entries belonging to inactive categories.
            if feature_name is None:
                continue

            profile["feature_totals"][feature_name] += float(
                entry.quantity
            )

        profile["total_emission"] += float(
            activity.carbon_footprint.total_emission
        )

        profile["submission_count"] += 1

    rows = []
    targets = []
    metadata_rows = []

    # ------------------------------------------------------------------
    # Convert consecutive monthly profiles into training transitions.
    #
    # Example:
    #
    # January profile
    #       ↓
    # February target
    #
    # February profile
    #       ↓
    # March target
    # ------------------------------------------------------------------
    for user_id in sorted(monthly_profiles):
        periods = sorted(
            monthly_profiles[user_id].keys()
        )

        for index in range(len(periods) - 1):
            feature_period = periods[index]
            target_period = periods[index + 1]

            # Only consecutive calendar months create a valid
            # next-month prediction pair.
            expected_target_period = (
                feature_period.replace(
                    year=(
                        feature_period.year
                        + (
                            1
                            if feature_period.month == 12
                            else 0
                        )
                    ),
                    month=(
                        1
                        if feature_period.month == 12
                        else feature_period.month + 1
                    ),
                )
            )

            if target_period != expected_target_period:
                continue

            previous_profile = monthly_profiles[user_id][
                feature_period
            ]

            row = {
                f"previous_{feature_name}": previous_profile[
                    "feature_totals"
                ][feature_name]
                for feature_name in canonical_feature_names
            }

            row["previous_total_emission"] = (
                previous_profile["total_emission"]
            )

            row["previous_submission_count"] = (
                previous_profile["submission_count"]
            )

            rows.append(row)

            targets.append(
                monthly_profiles[user_id][target_period][
                    "total_emission"
                ]
            )

            metadata_rows.append(
                {
                    "user_id": user_id,
                    "feature_period": feature_period,
                    "target_period": target_period,
                }
            )

    if not rows:
        raise MLDataError(
            "No consecutive monthly activity periods are available "
            "for temporal prediction training."
        )

    X = pd.DataFrame(rows)

    y = pd.Series(
        targets,
        name="next_total_emission",
    )

    metadata = pd.DataFrame(
        metadata_rows
    )

    return X, y, metadata

def get_segmentation_dataset():
    """
    Build the K-Means user-level segmentation dataset.

    Each row represents one user.

    Feature values represent the user's average historical
    activity quantities by active category.

    Additional behavioural features:
        - avg_total_emission
        - submission_count

    Returns:
        X: pandas.DataFrame
            User-level numerical features.

        metadata: pandas.DataFrame
            User identifiers used to map clusters back to users.
    """

    activities = list(get_completed_activities())

    if not activities:
        raise MLDataError(
            "No completed carbon activities with calculated footprints "
            "are available for user segmentation."
        )

    # Build the canonical feature schema from active categories.
    active_categories = (
        ActivityCategory.objects
        .filter(is_active=True)
        .order_by("display_order", "name")
    )

    feature_name_map = {}

    for category in active_categories:
        feature_name = normalize_feature_name(category.name)

        if feature_name in feature_name_map.values():
            raise MLDataError(
                f"Activity categories produce duplicate ML feature name: "
                f"'{feature_name}'."
            )

        feature_name_map[category.id] = feature_name

    if not feature_name_map:
        raise MLDataError(
            "No active activity categories are available "
            "for ML feature generation."
        )

    canonical_feature_names = sorted(feature_name_map.values())

    # Store per-user observations.
    user_records = {}

    for activity in activities:
        user_id = activity.user_id

        if user_id not in user_records:
            user_records[user_id] = {
                "feature_totals": {
                    feature_name: 0.0
                    for feature_name in canonical_feature_names
                },
                "total_emission": 0.0,
                "submission_count": 0,
            }

        user_data = user_records[user_id]

        for entry in activity.entries.all():
            feature_name = feature_name_map.get(entry.category_id)

            # Ignore entries belonging to inactive categories.
            if feature_name is None:
                continue

            user_data["feature_totals"][feature_name] += float(
                entry.quantity
            )

        user_data["total_emission"] += float(
            activity.carbon_footprint.total_emission
        )

        user_data["submission_count"] += 1

    if not user_records:
        raise MLDataError(
            "Completed activities contain no usable user data "
            "for segmentation."
        )

    rows = []
    metadata_rows = []

    for user_id in sorted(user_records):
        user_data = user_records[user_id]

        submission_count = user_data["submission_count"]

        if submission_count <= 0:
            continue

        row = {
            feature_name: (
                user_data["feature_totals"][feature_name]
                / submission_count
            )
            for feature_name in canonical_feature_names
        }

        row["avg_total_emission"] = (
            user_data["total_emission"]
            / submission_count
        )

        row["submission_count"] = submission_count

        rows.append(row)

        metadata_rows.append(
            {
                "user_id": user_id,
            }
        )

    X = pd.DataFrame(
        rows,
        columns=[
            *canonical_feature_names,
            "avg_total_emission",
            "submission_count",
        ],
    )

    metadata = pd.DataFrame(metadata_rows)

    if X.empty:
        raise MLDataError(
            "No valid user-level feature records are available "
            "for segmentation."
        )

    return X, metadata