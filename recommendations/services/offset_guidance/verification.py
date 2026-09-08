from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from django.utils import timezone

from recommendations.models import OffsetProject


VERIFICATION_FRESH_DAYS = 30
VERIFICATION_AGING_DAYS = 90


class VerificationState:
    """
    Normalized verification-age states used by CarbonIQ.

    These states describe how recently CarbonIQ checked the stored
    project information against its source registry.

    They do NOT certify the environmental quality of the project.
    """

    FRESH = "FRESH"
    AGING = "AGING"
    STALE = "STALE"
    UNAVAILABLE = "UNAVAILABLE"


@dataclass(frozen=True)
class OffsetVerification:
    """
    Traceability information for one offset project.

    This is a presentation/service-layer object. It does not modify
    OffsetProject or make claims beyond the information stored by
    CarbonIQ.
    """

    registry: str
    registry_project_id: str
    registry_url: str
    certification_documents_url: str
    source_last_verified_at: datetime | None
    project_status: str
    state: str
    state_label: str
    days_since_verification: int | None

    @property
    def status_label(self) -> str:
        """
        Return the human-readable normalized project status.
        """

        try:
            return OffsetProject.ProjectStatus(
                self.project_status
            ).label

        except ValueError:
            return self.project_status or "Unknown"

    @property
    def has_certification_documents(self) -> bool:
        """
        Return whether a public certification/document URL exists.
        """

        return bool(
            self.certification_documents_url
        )


def get_verification_state(
    source_last_verified_at: datetime | None,
    *,
    now: datetime | None = None,
) -> tuple[str, str, int | None]:
    """
    Classify the age of the last source verification.

    Fresh:
        0–30 days

    Aging:
        31–90 days

    Stale:
        more than 90 days

    Unavailable:
        no verification timestamp is available

    This describes verification recency only. It is not a
    certification-quality rating.
    """

    if source_last_verified_at is None:
        return (
            VerificationState.UNAVAILABLE,
            "Verification date unavailable",
            None,
        )

    comparison_time = now or timezone.now()

    if timezone.is_naive(comparison_time):
        comparison_time = timezone.make_aware(
            comparison_time,
            timezone.get_current_timezone(),
        )

    if timezone.is_naive(source_last_verified_at):
        source_last_verified_at = timezone.make_aware(
            source_last_verified_at,
            timezone.get_current_timezone(),
        )

    elapsed = comparison_time - source_last_verified_at

    days_since_verification = max(
        0,
        elapsed.days,
    )

    if days_since_verification <= VERIFICATION_FRESH_DAYS:
        return (
            VerificationState.FRESH,
            "Recently verified",
            days_since_verification,
        )

    if days_since_verification <= VERIFICATION_AGING_DAYS:
        return (
            VerificationState.AGING,
            "Verification aging",
            days_since_verification,
        )

    return (
        VerificationState.STALE,
        "Verification is old",
        days_since_verification,
    )


def build_offset_verification(
    project: OffsetProject,
    *,
    now: datetime | None = None,
) -> OffsetVerification:
    """
    Build a traceability/verification view of an OffsetProject.

    No source information is invented or changed here.
    """

    (
        state,
        state_label,
        days_since_verification,
    ) = get_verification_state(
        project.source_last_verified_at,
        now=now,
    )

    return OffsetVerification(
        registry=project.registry,
        registry_project_id=project.registry_project_id,
        registry_url=project.registry_url,
        certification_documents_url=(
            project.certification_documents_url
        ),
        source_last_verified_at=(
            project.source_last_verified_at
        ),
        project_status=project.status,
        state=state,
        state_label=state_label,
        days_since_verification=(
            days_since_verification
        ),
    )