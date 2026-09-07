from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from gamification.models import Achievement, Challenge, UserAchievement, UserChallenge
from gamification.services.achievements import AchievementEvaluationResult
from gamification.services.engagement import (
    EngagementRefreshResult,
    EngagementSnapshot,
    build_engagement_snapshot,
    refresh_engagement,
)
from gamification.services.score import EcoScore


class EngagementServiceTests(TestCase):
    """
    Tests for the E8 engagement coordinator.

    The coordinator must:
    - aggregate the existing E8 services
    - keep snapshot construction read-only
    - expose user-specific achievements/challenges
    - explicitly refresh achievements only through refresh_engagement()
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="engagement@example.com",
            full_name="Engagement User",
            password="TestPassword123!",
        )

        cls.other_user = CustomUser.objects.create_user(
            email="other-engagement@example.com",
            full_name="Other Engagement User",
            password="TestPassword123!",
        )

        cls.achievement = Achievement.objects.create(
            code="TEST_ACHIEVEMENT",
            name="Test Achievement",
            description="Achievement used by engagement tests.",
            icon="fa-leaf",
            is_active=True,
        )

        cls.challenge = Challenge.objects.create(
            code="TEST_CHALLENGE",
            title="Test Challenge",
            description="Challenge used by engagement tests.",
            metric=Challenge.Metric.SUSTAINABLE_ACTIONS,
            target=Decimal("3"),
            start_date="2026-09-01",
            end_date="2026-12-31",
            is_active=True,
        )

    def test_build_snapshot_returns_expected_type(self):
        """
        Snapshot construction should return EngagementSnapshot.
        """

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("70.00"),
                emission_performance=Decimal("80.00"),
                improvement_trend=Decimal("60.00"),
                sustainable_behaviour=Decimal("75.00"),
                engagement_progress=Decimal("50.00"),
            ),
        ):
            result = build_engagement_snapshot(self.user)

        self.assertIsInstance(
            result,
            EngagementSnapshot,
        )

    def test_snapshot_includes_currently_available_challenges(self):
        """
        The engagement snapshot should expose globally available
        challenges for discovery.
        """

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("50.00"),
                emission_performance=Decimal("50.00"),
                improvement_trend=Decimal("50.00"),
                sustainable_behaviour=Decimal("50.00"),
                engagement_progress=Decimal("50.00"),
            ),
        ), patch(
            "gamification.services.engagement.get_active_challenges",
            return_value=[self.challenge],
        ) as mock_active_challenges:
            result = build_engagement_snapshot(self.user)

        self.assertEqual(
            result.available_challenges,
            (self.challenge,),
        )

        mock_active_challenges.assert_called_once_with()
    
    def test_snapshot_uses_requested_users_data_only(self):
        """
        Achievements and challenges belonging to another user must not
        appear in the current user's snapshot.
        """

        UserAchievement.objects.create(
            user=self.user,
            achievement=self.achievement,
        )

        UserAchievement.objects.create(
            user=self.other_user,
            achievement=self.achievement,
        )

        first_challenge = UserChallenge.objects.create(
            user=self.user,
            challenge=self.challenge,
            progress=Decimal("2"),
        )

        second_challenge = UserChallenge.objects.create(
            user=self.other_user,
            challenge=self.challenge,
            progress=Decimal("3"),
            completed=True,
        )

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("70.00"),
                emission_performance=Decimal("80.00"),
                improvement_trend=Decimal("60.00"),
                sustainable_behaviour=Decimal("75.00"),
                engagement_progress=Decimal("50.00"),
            ),
        ):
            result = build_engagement_snapshot(self.user)

        self.assertEqual(
            len(result.earned_achievements),
            1,
        )

        self.assertEqual(
            result.earned_achievements[0].user,
            self.user,
        )

        self.assertEqual(
            len(result.active_challenges),
            1,
        )

        self.assertEqual(
            result.active_challenges[0].pk,
            first_challenge.pk,
        )

        self.assertNotIn(
            second_challenge.pk,
            {
                challenge.pk
                for challenge in result.active_challenges
            },
        )

    def test_completed_challenges_are_exposed_separately(self):
        """
        Completed challenges should be available in the completed
        collection as well as the user's overall challenge history.
        """

        UserChallenge.objects.create(
            user=self.user,
            challenge=self.challenge,
            progress=Decimal("3"),
            completed=True,
        )

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("90.00"),
                emission_performance=Decimal("90.00"),
                improvement_trend=Decimal("90.00"),
                sustainable_behaviour=Decimal("90.00"),
                engagement_progress=Decimal("90.00"),
            ),
        ):
            result = build_engagement_snapshot(self.user)

        self.assertEqual(
            len(result.completed_challenges),
            1,
        )

        self.assertTrue(
            result.completed_challenges[0].completed,
        )

    def test_completed_challenges_are_not_returned_as_active(self):
        """
        A completed challenge must appear only in the completed collection,
        not in the active collection.
        """

        UserChallenge.objects.create(
            user=self.user,
            challenge=self.challenge,
            progress=Decimal("3"),
            completed=True,
        )

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("90.00"),
                emission_performance=Decimal("90.00"),
                improvement_trend=Decimal("90.00"),
                sustainable_behaviour=Decimal("90.00"),
                engagement_progress=Decimal("90.00"),
            ),
        ):
            result = build_engagement_snapshot(self.user)

        self.assertEqual(
            result.active_challenges,
            (),
        )

        self.assertEqual(
            len(result.completed_challenges),
            1,
        )

        self.assertTrue(
            result.completed_challenges[0].completed,
    )

    def test_inactive_challenges_are_not_returned_as_active(self):
        """
        User participation in an inactive challenge should not be
        represented as an active challenge.
        """

        inactive = Challenge.objects.create(
            code="INACTIVE_TEST_CHALLENGE",
            title="Inactive Challenge",
            description="Inactive challenge.",
            metric=Challenge.Metric.SUSTAINABLE_ACTIONS,
            target=Decimal("3"),
            start_date="2026-09-01",
            end_date="2026-12-31",
            is_active=False,
        )

        UserChallenge.objects.create(
            user=self.user,
            challenge=inactive,
            progress=Decimal("1"),
        )

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("70.00"),
                emission_performance=Decimal("70.00"),
                improvement_trend=Decimal("70.00"),
                sustainable_behaviour=Decimal("70.00"),
                engagement_progress=Decimal("70.00"),
            ),
        ):
            result = build_engagement_snapshot(self.user)

        self.assertEqual(
            len(result.active_challenges),
            0,
        )

    @patch(
        "gamification.services.engagement.calculate_eco_score",
    )
    @patch(
        "gamification.services.engagement.evaluate_achievements",
    )
    def test_refresh_explicitly_evaluates_achievements(
        self,
        mock_evaluate,
        mock_score,
    ):
        """
        refresh_engagement() must explicitly evaluate achievements.
        """

        mock_score.return_value = EcoScore(
            overall_score=Decimal("75.00"),
            emission_performance=Decimal("80.00"),
            improvement_trend=Decimal("70.00"),
            sustainable_behaviour=Decimal("75.00"),
            engagement_progress=Decimal("70.00"),
        )

        mock_evaluate.return_value = AchievementEvaluationResult(
            earned=(self.achievement,),
            newly_awarded=(self.achievement,),
        )

        result = refresh_engagement(self.user)

        self.assertIsInstance(
            result,
            EngagementRefreshResult,
        )

        mock_evaluate.assert_called_once_with(
            self.user,
        )

        self.assertEqual(
            result.achievement_evaluation.newly_awarded,
            (self.achievement,),
        )

    @patch(
        "gamification.services.engagement.calculate_eco_score",
    )
    @patch(
        "gamification.services.engagement.evaluate_achievements",
    )
    def test_refresh_returns_updated_snapshot(
        self,
        mock_evaluate,
        mock_score,
    ):
        """
        The refresh operation should evaluate achievements first and
        then construct the resulting snapshot.
        """

        mock_score.return_value = EcoScore(
            overall_score=Decimal("82.00"),
            emission_performance=Decimal("85.00"),
            improvement_trend=Decimal("80.00"),
            sustainable_behaviour=Decimal("75.00"),
            engagement_progress=Decimal("90.00"),
        )

        mock_evaluate.return_value = AchievementEvaluationResult(
            earned=(self.achievement,),
            newly_awarded=(self.achievement,),
        )

        result = refresh_engagement(self.user)

        self.assertEqual(
            result.snapshot.eco_score.overall_score,
            Decimal("82.00"),
        )

        self.assertEqual(
            len(result.snapshot.earned_achievements),
            0,
        )

        self.assertEqual(
            len(result.achievement_evaluation.earned),
            1,
        )

    def test_build_snapshot_does_not_create_achievement_records(self):
        """
        Building a snapshot must remain read-only.
        """

        self.assertEqual(
            UserAchievement.objects.filter(
                user=self.user,
            ).count(),
            0,
        )

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("50.00"),
                emission_performance=Decimal("50.00"),
                improvement_trend=Decimal("50.00"),
                sustainable_behaviour=Decimal("50.00"),
                engagement_progress=Decimal("50.00"),
            ),
        ):
            build_engagement_snapshot(self.user)

        self.assertEqual(
            UserAchievement.objects.filter(
                user=self.user,
            ).count(),
            0,
        )

    def test_build_snapshot_does_not_create_challenge_records(self):
        """
        Snapshot construction must not automatically enrol the user
        into challenges.
        """

        self.assertEqual(
            UserChallenge.objects.filter(
                user=self.user,
            ).count(),
            0,
        )

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("50.00"),
                emission_performance=Decimal("50.00"),
                improvement_trend=Decimal("50.00"),
                sustainable_behaviour=Decimal("50.00"),
                engagement_progress=Decimal("50.00"),
            ),
        ):
            build_engagement_snapshot(self.user)

        self.assertEqual(
            UserChallenge.objects.filter(
                user=self.user,
            ).count(),
            0,
        )

    def test_empty_user_snapshot_is_safe(self):
        """
        A new user with no achievements or challenge participation
        should still receive a valid snapshot.
        """

        with patch(
            "gamification.services.engagement.calculate_eco_score",
            return_value=EcoScore(
                overall_score=Decimal("50.00"),
                emission_performance=Decimal("50.00"),
                improvement_trend=Decimal("50.00"),
                sustainable_behaviour=Decimal("50.00"),
                engagement_progress=Decimal("50.00"),
            ),
        ):
            result = build_engagement_snapshot(self.user)

        self.assertEqual(
            result.eco_score.overall_score,
            Decimal("50.00"),
        )

        self.assertEqual(
            result.earned_achievements,
            (),
        )
        
        self.assertEqual(
            result.available_challenges,
            (self.challenge,),
        )

        self.assertEqual(
            result.active_challenges,
            (),
        )

        self.assertEqual(
            result.completed_challenges,
            (),
        )

    @patch(
        "gamification.services.engagement.calculate_eco_score",
    )
    @patch(
        "gamification.services.engagement.evaluate_achievements",
    )
    def test_refresh_does_not_directly_update_challenge_progress(
        self,
        mock_evaluate,
        mock_score,
    ):
        """
        Challenge progress remains the responsibility of the challenge
        service; the engagement coordinator must not silently modify it.
        """

        mock_score.return_value = EcoScore(
            overall_score=Decimal("60.00"),
            emission_performance=Decimal("60.00"),
            improvement_trend=Decimal("60.00"),
            sustainable_behaviour=Decimal("60.00"),
            engagement_progress=Decimal("60.00"),
        )

        mock_evaluate.return_value = AchievementEvaluationResult(
            earned=(),
            newly_awarded=(),
        )

        refresh_engagement(self.user)

        self.assertEqual(
            UserChallenge.objects.filter(
                user=self.user,
            ).count(),
            0,
        )