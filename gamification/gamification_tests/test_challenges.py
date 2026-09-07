from datetime import date, timedelta
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from gamification.models import Challenge, UserChallenge
from gamification.services.challenges import (
    calculate_challenge_progress,
    get_active_challenges,
    is_challenge_available,
    join_challenge,
    update_challenge_progress,
)
from recommendations.models import Recommendation, UserRecommendation


class ChallengeServiceTests(TestCase):
    """
    Tests for E8 challenge creation, availability, progress,
    participation, completion, and idempotent updates.
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="challenge@example.com",
            full_name="Challenge User",
            password="TestPassword123!",
        )

        cls.other_user = CustomUser.objects.create_user(
            email="other-challenge@example.com",
            full_name="Other Challenge User",
            password="TestPassword123!",
        )

        cls.sustainability_recommendation = (
            Recommendation.objects.create(
                title="Use Public Transport",
                description=(
                    "Prefer public transport for suitable journeys."
                ),
                action_type=Recommendation.ActionType.SUSTAINABILITY,
                priority=50,
                is_active=True,
            )
        )

    def create_challenge(
        self,
        *,
        code="TEST_CHALLENGE",
        metric=Challenge.Metric.SUSTAINABLE_ACTIONS,
        target=Decimal("3"),
        start_date=None,
        end_date=None,
        is_active=True,
    ):
        today = date(2026, 9, 7)

        if start_date is None:
            start_date = today - timedelta(days=1)

        if end_date is None:
            end_date = today + timedelta(days=30)

        return Challenge.objects.create(
            code=code,
            title="Test Challenge",
            description="Challenge for automated testing.",
            metric=metric,
            target=target,
            start_date=start_date,
            end_date=end_date,
            is_active=is_active,
        )

    def test_available_challenge_is_detected(self):
        challenge = self.create_challenge()

        self.assertTrue(
            is_challenge_available(
                challenge,
                today=date(2026, 9, 7),
            )
        )

    def test_challenge_before_start_date_is_unavailable(self):
        challenge = self.create_challenge(
            start_date=date(2026, 9, 8),
        )

        self.assertFalse(
            is_challenge_available(
                challenge,
                today=date(2026, 9, 7),
            )
        )

    def test_challenge_after_end_date_is_unavailable(self):
        challenge = self.create_challenge(
            end_date=date(2026, 9, 6),
        )

        self.assertFalse(
            is_challenge_available(
                challenge,
                today=date(2026, 9, 7),
            )
        )

    def test_inactive_challenge_is_unavailable(self):
        challenge = self.create_challenge(
            is_active=False,
        )

        self.assertFalse(
            is_challenge_available(
                challenge,
                today=date(2026, 9, 7),
            )
        )

    def test_get_active_challenges_returns_only_available_challenges(self):
        active = self.create_challenge(
            code="ACTIVE_CHALLENGE",
        )

        self.create_challenge(
            code="FUTURE_CHALLENGE",
            start_date=date(2026, 9, 8),
        )

        self.create_challenge(
            code="EXPIRED_CHALLENGE",
            end_date=date(2026, 9, 6),
        )

        self.create_challenge(
            code="INACTIVE_CHALLENGE",
            is_active=False,
        )

        result = get_active_challenges(
            today=date(2026, 9, 7),
        )

        self.assertEqual(
            list(result),
            [active],
        )

    @patch(
        "gamification.services.challenges._calculate_sustainable_actions",
        return_value=Decimal("2"),
    )
    def test_sustainable_actions_progress_is_returned(
        self,
        mock_actions,
    ):
        challenge = self.create_challenge(
            metric=Challenge.Metric.SUSTAINABLE_ACTIONS,
            target=Decimal("3"),
        )

        result = calculate_challenge_progress(
            challenge,
            self.user,
        )

        self.assertEqual(
            result.raw_progress,
            Decimal("2"),
        )

        self.assertEqual(
            result.progress,
            Decimal("2"),
        )

        self.assertFalse(
            result.completed,
        )

        mock_actions.assert_called_once_with(
            self.user,
        )

    @patch(
        "gamification.services.challenges._calculate_sustainable_actions",
        return_value=Decimal("5"),
    )
    def test_progress_is_capped_at_target(
        self,
        mock_actions,
    ):
        challenge = self.create_challenge(
            metric=Challenge.Metric.SUSTAINABLE_ACTIONS,
            target=Decimal("3"),
        )

        result = calculate_challenge_progress(
            challenge,
            self.user,
        )

        self.assertEqual(
            result.raw_progress,
            Decimal("5"),
        )

        self.assertEqual(
            result.progress,
            Decimal("3"),
        )

        self.assertTrue(
            result.completed,
        )

    @patch(
        "gamification.services.challenges._calculate_emission_reduction",
        return_value=Decimal("15"),
    )
    def test_emission_reduction_challenge_reaches_target(
        self,
        mock_reduction,
    ):
        challenge = self.create_challenge(
            metric=Challenge.Metric.EMISSION_REDUCTION,
            target=Decimal("10"),
        )

        result = calculate_challenge_progress(
            challenge,
            self.user,
        )

        self.assertEqual(
            result.raw_progress,
            Decimal("15"),
        )

        self.assertEqual(
            result.progress,
            Decimal("10"),
        )

        self.assertTrue(
            result.completed,
        )

        mock_reduction.assert_called_once_with(
            self.user,
        )

    @patch(
        "gamification.services.challenges._calculate_monthly_improvements",
        return_value=Decimal("2"),
    )
    def test_monthly_improvement_challenge_progress(
        self,
        mock_improvements,
    ):
        challenge = self.create_challenge(
            metric=Challenge.Metric.MONTHLY_IMPROVEMENT,
            target=Decimal("3"),
        )

        result = calculate_challenge_progress(
            challenge,
            self.user,
        )

        self.assertEqual(
            result.raw_progress,
            Decimal("2"),
        )

        self.assertEqual(
            result.progress,
            Decimal("2"),
        )

        self.assertFalse(
            result.completed,
        )

    @patch(
        "gamification.services.challenges._calculate_low_emission_periods",
        return_value=Decimal("2"),
    )
    def test_low_emission_period_progress(
        self,
        mock_low_emission,
    ):
        challenge = self.create_challenge(
            metric=Challenge.Metric.LOW_EMISSION_PERIOD,
            target=Decimal("2"),
        )

        result = calculate_challenge_progress(
            challenge,
            self.user,
        )

        self.assertEqual(
            result.raw_progress,
            Decimal("2"),
        )

        self.assertEqual(
            result.progress,
            Decimal("2"),
        )

        self.assertTrue(
            result.completed,
        )

    @patch(
        "gamification.services.challenges._calculate_sustainable_actions",
        return_value=Decimal("5"),
    )
    def test_zero_target_challenge_is_safe(
        self,
        mock_actions,
    ):
        challenge = self.create_challenge(
            target=Decimal("0"),
        )

        result = calculate_challenge_progress(
            challenge,
            self.user,
        )

        self.assertEqual(
            result.raw_progress,
            Decimal("5"),
        )

        self.assertEqual(
            result.progress,
            Decimal("0"),
        )

        self.assertTrue(
            result.completed,
        )

    def test_user_can_join_available_challenge(self):
        challenge = self.create_challenge()

        user_challenge = join_challenge(
            self.user,
            challenge,
            today=date(2026, 9, 7),
        )

        self.assertEqual(
            user_challenge.user,
            self.user,
        )

        self.assertEqual(
            user_challenge.challenge,
            challenge,
        )

        self.assertFalse(
            user_challenge.completed,
        )

    def test_joining_same_challenge_is_idempotent(self):
        challenge = self.create_challenge()

        first = join_challenge(
            self.user,
            challenge,
            today=date(2026, 9, 7),
        )

        second = join_challenge(
            self.user,
            challenge,
            today=date(2026, 9, 7),
        )

        self.assertEqual(
            first.pk,
            second.pk,
        )

        self.assertEqual(
            UserChallenge.objects.filter(
                user=self.user,
                challenge=challenge,
            ).count(),
            1,
        )

    def test_expired_challenge_cannot_be_joined(self):
        challenge = self.create_challenge(
            end_date=date(2026, 9, 6),
        )

        with self.assertRaisesMessage(
            ValueError,
            "Challenge is not currently available.",
        ):
            join_challenge(
                self.user,
                challenge,
                today=date(2026, 9, 7),
            )

    @patch(
        "gamification.services.challenges.calculate_challenge_progress",
    )
    def test_update_progress_persists_progress(
        self,
        mock_progress,
    ):
        challenge = self.create_challenge(
            target=Decimal("3"),
        )

        user_challenge = UserChallenge.objects.create(
            user=self.user,
            challenge=challenge,
        )

        mock_progress.return_value.raw_progress = Decimal("2")
        mock_progress.return_value.progress = Decimal("2")
        mock_progress.return_value.completed = False

        result = update_challenge_progress(
            user_challenge,
        )

        user_challenge.refresh_from_db()

        self.assertEqual(
            result.progress,
            Decimal("2"),
        )

        self.assertFalse(
            user_challenge.completed,
        )

        self.assertIsNone(
            user_challenge.completed_at,
        )

    @patch(
        "gamification.services.challenges.calculate_challenge_progress",
    )
    def test_completion_sets_completion_timestamp(
        self,
        mock_progress,
    ):
        challenge = self.create_challenge(
            target=Decimal("3"),
        )

        user_challenge = UserChallenge.objects.create(
            user=self.user,
            challenge=challenge,
        )

        mock_progress.return_value.raw_progress = Decimal("3")
        mock_progress.return_value.progress = Decimal("3")
        mock_progress.return_value.completed = True

        before = timezone.now()

        update_challenge_progress(
            user_challenge,
        )

        after = timezone.now()

        user_challenge.refresh_from_db()

        self.assertTrue(
            user_challenge.completed,
        )

        self.assertIsNotNone(
            user_challenge.completed_at,
        )

        self.assertGreaterEqual(
            user_challenge.completed_at,
            before,
        )

        self.assertLessEqual(
            user_challenge.completed_at,
            after,
        )

    @patch(
        "gamification.services.challenges.calculate_challenge_progress",
    )
    def test_existing_completion_timestamp_is_preserved(
        self,
        mock_progress,
    ):
        challenge = self.create_challenge(
            target=Decimal("3"),
        )

        original_timestamp = timezone.now() - timedelta(
            hours=1,
        )

        user_challenge = UserChallenge.objects.create(
            user=self.user,
            challenge=challenge,
            progress=Decimal("3"),
            completed=True,
            completed_at=original_timestamp,
        )

        mock_progress.return_value.raw_progress = Decimal("5")
        mock_progress.return_value.progress = Decimal("3")
        mock_progress.return_value.completed = True

        update_challenge_progress(
            user_challenge,
        )

        user_challenge.refresh_from_db()

        self.assertEqual(
            user_challenge.completed_at,
            original_timestamp,
        )

    def test_sustainability_action_count_excludes_offset_recommendations(
        self,
    ):
        sustainability = Recommendation.objects.create(
            title="Reduce Driving",
            description="Walk or cycle for short journeys.",
            action_type=Recommendation.ActionType.SUSTAINABILITY,
            priority=50,
            is_active=True,
        )

        offset = Recommendation.objects.create(
            title="Example Offset",
            description="Example offset guidance.",
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
            is_active=True,
        )

        for index in range(2):
            UserRecommendation.objects.create(
                user=self.user,
                recommendation=sustainability,
                score=Decimal("80") + index,
                reason="Sustainability action.",
                status=UserRecommendation.Status.COMPLETED,
            )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=sustainability,
            score=Decimal("70"),
            reason="Active action.",
            status=UserRecommendation.Status.ACTIVE,
        )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=offset,
            score=Decimal("90"),
            reason="Offset guidance.",
            status=UserRecommendation.Status.COMPLETED,
        )

        from gamification.services.challenges import (
            _calculate_sustainable_actions,
        )

        self.assertEqual(
            _calculate_sustainable_actions(self.user),
            Decimal("2"),
        )

    def test_user_challenge_records_are_user_specific(self):
        challenge = self.create_challenge()

        first = join_challenge(
            self.user,
            challenge,
            today=date(2026, 9, 7),
        )

        second = join_challenge(
            self.other_user,
            challenge,
            today=date(2026, 9, 7),
        )

        self.assertNotEqual(
            first.pk,
            second.pk,
        )

        self.assertEqual(
            UserChallenge.objects.filter(
                user=self.user,
            ).count(),
            1,
        )

        self.assertEqual(
            UserChallenge.objects.filter(
                user=self.other_user,
            ).count(),
            1,
        )