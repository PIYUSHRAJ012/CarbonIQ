from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from decimal import Decimal
from typing import Iterable
from django.utils import timezone

from django.contrib.auth import get_user_model
from django.db import transaction
from django.core.exceptions import ValidationError
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
)
from carbon.services.calculator import CarbonCalculationService
from carbon.services.emission import EmissionFactorService


DEMO_EMAIL_DOMAIN = "@demo.carboniq.local"
DEMO_EMAIL_PREFIX = "demo_user_"

DEMO_PASSWORD = "CarbonIQDemo123!"

DEMO_USER_COUNT = 20
DEMO_MONTH_COUNT = 12


@dataclass(frozen=True)
class DemoProfile:
    """
    Defines the behavioural pattern used to generate
    one synthetic CarbonIQ user.
    """

    name: str
    electricity: Decimal
    transportation: Decimal
    petrol: Decimal
    diesel: Decimal
    rice_grain: Decimal
    legumes: Decimal
    milk: Decimal
    tofu: Decimal
    fruit: Decimal
    vegetables: Decimal
    clothing: Decimal
    footwear: Decimal
    waste: Decimal


DEMO_PROFILES = (
    DemoProfile(
        name="LOW",
        electricity=Decimal("45"),
        transportation=Decimal("30"),
        petrol=Decimal("2"),
        diesel=Decimal("0"),
        rice_grain=Decimal("2"),
        legumes=Decimal("1"),
        milk=Decimal("4"),
        tofu=Decimal("1"),
        fruit=Decimal("5"),
        vegetables=Decimal("7"),
        clothing=Decimal("250"),
        footwear=Decimal("150"),
        waste=Decimal("5"),
    ),
    DemoProfile(
        name="BALANCED",
        electricity=Decimal("90"),
        transportation=Decimal("80"),
        petrol=Decimal("8"),
        diesel=Decimal("2"),
        rice_grain=Decimal("5"),
        legumes=Decimal("2"),
        milk=Decimal("8"),
        tofu=Decimal("2"),
        fruit=Decimal("8"),
        vegetables=Decimal("10"),
        clothing=Decimal("700"),
        footwear=Decimal("350"),
        waste=Decimal("10"),
    ),
    DemoProfile(
        name="ELECTRICITY_HEAVY",
        electricity=Decimal("220"),
        transportation=Decimal("50"),
        petrol=Decimal("3"),
        diesel=Decimal("0"),
        rice_grain=Decimal("4"),
        legumes=Decimal("2"),
        milk=Decimal("7"),
        tofu=Decimal("2"),
        fruit=Decimal("7"),
        vegetables=Decimal("9"),
        clothing=Decimal("500"),
        footwear=Decimal("300"),
        waste=Decimal("9"),
    ),
    DemoProfile(
        name="TRANSPORT_HEAVY",
        electricity=Decimal("85"),
        transportation=Decimal("320"),
        petrol=Decimal("55"),
        diesel=Decimal("10"),
        rice_grain=Decimal("4"),
        legumes=Decimal("2"),
        milk=Decimal("6"),
        tofu=Decimal("2"),
        fruit=Decimal("6"),
        vegetables=Decimal("8"),
        clothing=Decimal("450"),
        footwear=Decimal("250"),
        waste=Decimal("12"),
    ),
    DemoProfile(
        name="FOOD_HEAVY",
        electricity=Decimal("75"),
        transportation=Decimal("60"),
        petrol=Decimal("5"),
        diesel=Decimal("1"),
        rice_grain=Decimal("15"),
        legumes=Decimal("8"),
        milk=Decimal("25"),
        tofu=Decimal("8"),
        fruit=Decimal("20"),
        vegetables=Decimal("25"),
        clothing=Decimal("350"),
        footwear=Decimal("200"),
        waste=Decimal("10"),
    ),
    DemoProfile(
        name="SHOPPING_HEAVY",
        electricity=Decimal("100"),
        transportation=Decimal("70"),
        petrol=Decimal("8"),
        diesel=Decimal("2"),
        rice_grain=Decimal("5"),
        legumes=Decimal("2"),
        milk=Decimal("7"),
        tofu=Decimal("2"),
        fruit=Decimal("7"),
        vegetables=Decimal("9"),
        clothing=Decimal("2500"),
        footwear=Decimal("1400"),
        waste=Decimal("12"),
    ),
    DemoProfile(
        name="WASTE_HEAVY",
        electricity=Decimal("95"),
        transportation=Decimal("75"),
        petrol=Decimal("7"),
        diesel=Decimal("2"),
        rice_grain=Decimal("5"),
        legumes=Decimal("2"),
        milk=Decimal("8"),
        tofu=Decimal("2"),
        fruit=Decimal("8"),
        vegetables=Decimal("10"),
        clothing=Decimal("450"),
        footwear=Decimal("250"),
        waste=Decimal("55"),
    ),
    DemoProfile(
        name="HIGH_EMISSION",
        electricity=Decimal("260"),
        transportation=Decimal("350"),
        petrol=Decimal("70"),
        diesel=Decimal("25"),
        rice_grain=Decimal("12"),
        legumes=Decimal("5"),
        milk=Decimal("18"),
        tofu=Decimal("5"),
        fruit=Decimal("12"),
        vegetables=Decimal("15"),
        clothing=Decimal("1800"),
        footwear=Decimal("900"),
        waste=Decimal("30"),
    ),
)


CATEGORY_ATTRIBUTE_MAP = {
    "Electricity": "electricity",
    "Transportation": "transportation",
    "Petrol": "petrol",
    "Diesel": "diesel",
    "Rice & Grain": "rice_grain",
    "Legumes": "legumes",
    "Milk": "milk",
    "Tofu": "tofu",
    "Fruit": "fruit",
    "Vegetables": "vegetables",
    "Clothing": "clothing",
    "Footwear": "footwear",
    "Waste": "waste",
}


def _month_start(year: int, month: int) -> date:
    return date(year, month, 1)


def _next_month(period: date) -> date:
    if period.month == 12:
        return period.replace(
            year=period.year + 1,
            month=1,
        )

    return period.replace(
        month=period.month + 1,
    )

def _month_timestamp(period: date) -> datetime:
    naive_datetime = datetime(
        year=period.year,
        month=period.month,
        day=15,
        hour=12,
        minute=0,
        second=0,
    )

    return timezone.make_aware(
        naive_datetime,
        timezone.get_current_timezone(),
    )

def _scale_quantity(
    quantity: Decimal,
    month_index: int,
    user_index: int,
) -> Decimal:
    """
    Produce deterministic month-to-month variation while
    preserving the user's underlying behavioural profile.
    """

    variation_pattern = (
        Decimal("0.96"),
        Decimal("1.00"),
        Decimal("1.04"),
        Decimal("0.98"),
        Decimal("1.06"),
        Decimal("1.02"),
    )

    factor = variation_pattern[
        (month_index + user_index) % len(variation_pattern)
    ]

    return (
        quantity * factor
    ).quantize(
        Decimal("0.01")
    )


def _get_profile(user_index: int) -> DemoProfile:
    return DEMO_PROFILES[
        user_index % len(DEMO_PROFILES)
    ]


def _get_categories() -> dict[str, ActivityCategory]:
    categories = ActivityCategory.objects.filter(
        name__in=CATEGORY_ATTRIBUTE_MAP.keys(),
        is_active=True,
    )

    category_map = {
        category.name: category
        for category in categories
    }

    missing = (
        set(CATEGORY_ATTRIBUTE_MAP.keys())
        - set(category_map.keys())
    )

    if missing:
        raise ValueError(
            "Required active CarbonIQ categories are missing: "
            f"{sorted(missing)}"
        )

    return category_map


def _get_or_create_demo_user(user_index: int):
    User = get_user_model()

    email = (
        f"{DEMO_EMAIL_PREFIX}"
        f"{user_index:02d}"
        f"{DEMO_EMAIL_DOMAIN}"
    )

    user, created = User.objects.get_or_create(
        email=email,
        defaults={
            "full_name": (
                f"CarbonIQ Demo User {user_index:02d}"
            ),
        },
    )

    if created:
        user.set_password(DEMO_PASSWORD)
        user.save(
            update_fields=["password"]
        )

    return user, created


def _delete_demo_users() -> int:
    User = get_user_model()

    deleted_count, _ = User.objects.filter(
        email__startswith=DEMO_EMAIL_PREFIX,
        email__endswith=DEMO_EMAIL_DOMAIN,
    ).delete()

    return deleted_count


@transaction.atomic
def seed_demo_dataset(
    *,
    user_count: int = DEMO_USER_COUNT,
    month_count: int = DEMO_MONTH_COUNT,
    start_period: date = date(2025, 10, 1),
    reset: bool = False,
) -> dict:
    """
    Generate a deterministic synthetic CarbonIQ ML dataset.

    Returns a summary dictionary suitable for a management command.
    """

    if user_count < 10:
        raise ValueError(
            "Demo dataset must contain at least 10 users "
            "for K-Means readiness."
        )

    if month_count < 2:
        raise ValueError(
            "Demo dataset must contain at least 2 consecutive "
            "months for temporal prediction."
        )

    deleted_users = 0

    if reset:
        deleted_users = _delete_demo_users()

    categories = _get_categories()

    created_users = 0
    reused_users = 0
    submissions_created = 0
    entries_created = 0

    period = start_period

    for user_index in range(
        1,
        user_count + 1,
    ):
        user, created = _get_or_create_demo_user(
            user_index
        )

        if created:
            created_users += 1
        else:
            reused_users += 1

        profile = _get_profile(
            user_index - 1
        )

        current_period = period

        for month_index in range(
            month_count
        ):
            activity = CarbonActivity.objects.create(
                user=user,
                status=CarbonActivity.Status.PENDING,
                notes=(
                    "Synthetic ML demonstration dataset."
                ),
            )

            activity_timestamp = _month_timestamp(
                current_period
            )

            CarbonActivity.objects.filter(
                pk=activity.pk
            ).update(
                created_at=activity_timestamp
            )

            activity.refresh_from_db(
                fields=["created_at"]
            )

            total_emission = Decimal("0.0000")

            for category_name, attribute_name in (
                CATEGORY_ATTRIBUTE_MAP.items()
            ):
                category = categories[
                    category_name
                ]

                base_quantity = getattr(
                    profile,
                    attribute_name,
                )

                quantity = _scale_quantity(
                    base_quantity,
                    month_index,
                    user_index,
                )

                if quantity <= 0:
                    continue

                try:
                    factor = (
                        EmissionFactorService.get_factor_for_date(
                            category=category,
                            reference_date=activity_timestamp.date(),
                        )
                    )

                except ValidationError:
                    # The category may legitimately have no
                    # historical factor for an earlier period.
                    # Omit that category from that month.
                    continue

                emission = (
                    CarbonCalculationService.calculate_emission(
                        quantity=quantity,
                        emission_factor=factor,
                    )
                )

                ActivityEntry.objects.create(
                    carbon_activity=activity,
                    category=category,
                    emission_factor=factor,
                    quantity=quantity,
                    emission_factor_snapshot=factor.factor,
                    entry_emission=emission,
                )

                total_emission += emission
                entries_created += 1

            if total_emission <= 0:
                raise ValueError(
                    "Generated demo submission has no valid "
                    f"emissions for user {user_index:02d} "
                    f"in {current_period:%Y-%m}."
                )

            CarbonFootprint.objects.create(
                carbon_activity=activity,
                total_emission=total_emission,
                calculation_version="v1.0",
            )

            CarbonActivity.objects.filter(
                pk=activity.pk
            ).update(
                status=CarbonActivity.Status.COMPLETED
            )

            submissions_created += 1

            current_period = _next_month(
                current_period
            )

    return {
        "created_users": created_users,
        "reused_users": reused_users,
        "submissions_created": submissions_created,
        "entries_created": entries_created,
        "user_count": user_count,
        "month_count": month_count,
        "start_period": start_period,
        "end_period": (
            current_period
            .replace(day=1)
            if "current_period" in locals()
            else start_period
        ),
        "password": DEMO_PASSWORD,
        "deleted_users": deleted_users,
    }