from datetime import date
from decimal import Decimal
from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from gamification.models import Achievement, UserAchievement
from gamification.services.achievements import (
    DEFAULT_ACHIEVEMENTS,
    AchievementEvaluationResult,
    evaluate_achievements,
    seed_default_achievements,
)
from recommendations.models import Recommendation, UserRecommendation


class AchievementServiceTests(TestCase):
    """
    Tests for the E8 achievement service.

    Coverage includes:
    - default achievement catalog
    - idempotent seeding
    - first footprint eligibility
    - tracking consistency
    - emission reduction
    - sustainability action completion
    - low-carbon benchmark achievement
    - inactive achievements
    - duplicate prevention
    - complete evaluation result
    """

    @classmethod
    def setUpTestData(cls):
        cls.user = CustomUser.objects.create_user(
            email="achievement@example.com",
            full_name="Achievement User",
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

        cls.offset_recommendation = Recommendation.objects.create(
            title="Support an Offset Project",
            description="Example offset guidance.",
            action_type=Recommendation.ActionType.OFFSET,
            priority=50,
            is_active=True,
        )

    def test_default_achievement_catalog_contains_expected_entries(self):
        """
        The default catalog should contain the five approved E8
        achievements.
        """

        achievements = seed_default_achievements()

        self.assertEqual(
            len(achievements),
            len(DEFAULT_ACHIEVEMENTS),
        )

        self.assertEqual(
            set(
                Achievement.objects.values_list(
                    "code",
                    flat=True,
                )
            ),
            {
                "FIRST_FOOTPRINT",
                "CONSISTENT_TRACKER",
                "EMISSION_REDUCER",
                "SUSTAINABILITY_ACTION_CHAMPION",
                "LOW_CARBON_MONTH",
            },
        )

    def test_seed_default_achievements_is_idempotent(self):
        """
        Re-seeding must not create duplicate achievement definitions.
        """

        first = seed_default_achievements()
        second = seed_default_achievements()

        self.assertEqual(
            len(first),
            len(second),
        )

        self.assertEqual(
            Achievement.objects.count(),
            len(DEFAULT_ACHIEVEMENTS),
        )

    @patch(
        "gamification.services.achievements._is_eligible",
        return_value=False,
    )
    def test_no_achievements_are_awarded_when_none_are_eligible(
        self,
        mock_is_eligible,
    ):
        """
        No eligible achievement should produce no earned records.
        """

        result = evaluate_achievements(self.user)

        self.assertIsInstance(
            result,
            AchievementEvaluationResult,
        )

        self.assertEqual(
            result.earned,
            (),
        )

        self.assertEqual(
            result.newly_awarded,
            (),
        )

        self.assertEqual(
            UserAchievement.objects.filter(
                user=self.user,
            ).count(),
            0,
        )

    @patch(
        "gamification.services.achievements._completed_footprint_count",
        return_value=1,
    )
    def test_first_footprint_is_eligible(
        self,
        mock_count,
    ):
        """
        One completed footprint should satisfy FIRST_FOOTPRINT.
        """

        from gamification.services.achievements import _is_eligible

        self.assertTrue(
            _is_eligible(
                code="FIRST_FOOTPRINT",
                user=self.user,
            )
        )

        mock_count.assert_called_once_with(self.user)

    @patch(
        "gamification.services.achievements._tracked_month_count",
        return_value=3,
    )
    def test_consistent_tracker_requires_three_months(
        self,
        mock_months,
    ):
        """
        Three tracked months should satisfy CONSISTENT_TRACKER.
        """

        from gamification.services.achievements import _is_eligible

        self.assertTrue(
            _is_eligible(
                code="CONSISTENT_TRACKER",
                user=self.user,
            )
        )

        mock_months.assert_called_once_with(self.user)

    @patch(
        "gamification.services.achievements._tracked_month_count",
        return_value=2,
    )
    def test_consistent_tracker_rejects_two_months(
        self,
        mock_months,
    ):
        """
        Two tracked months should not satisfy CONSISTENT_TRACKER.
        """

        from gamification.services.achievements import _is_eligible

        self.assertFalse(
            _is_eligible(
                code="CONSISTENT_TRACKER",
                user=self.user,
            )
        )

        mock_months.assert_called_once_with(self.user)

    @patch(
        "gamification.services.achievements._has_emission_reduction",
        return_value=True,
    )
    def test_emission_reducer_is_eligible(
        self,
        mock_reduction,
    ):
        """
        A qualifying emission reduction should satisfy
        EMISSION_REDUCER.
        """

        from gamification.services.achievements import _is_eligible

        self.assertTrue(
            _is_eligible(
                code="EMISSION_REDUCER",
                user=self.user,
            )
        )

        mock_reduction.assert_called_once_with(self.user)

    @patch(
        "gamification.services.achievements._completed_sustainability_action_count",
        return_value=3,
    )
    def test_sustainability_action_champion_requires_three_actions(
        self,
        mock_actions,
    ):
        """
        Three completed sustainability recommendations should satisfy
        SUSTAINABILITY_ACTION_CHAMPION.
        """

        from gamification.services.achievements import _is_eligible

        self.assertTrue(
            _is_eligible(
                code="SUSTAINABILITY_ACTION_CHAMPION",
                user=self.user,
            )
        )

        mock_actions.assert_called_once_with(self.user)

    @patch(
        "gamification.services.achievements._completed_sustainability_action_count",
        return_value=2,
    )
    def test_sustainability_action_champion_rejects_two_actions(
        self,
        mock_actions,
    ):
        """
        Two completed sustainability recommendations are insufficient.
        """

        from gamification.services.achievements import _is_eligible

        self.assertFalse(
            _is_eligible(
                code="SUSTAINABILITY_ACTION_CHAMPION",
                user=self.user,
            )
        )

        mock_actions.assert_called_once_with(self.user)

    @patch(
        "gamification.services.achievements._has_low_carbon_month",
        return_value=True,
    )
    def test_low_carbon_month_is_eligible(
        self,
        mock_low_carbon,
    ):
        """
        A qualifying benchmark comparison should satisfy
        LOW_CARBON_MONTH.
        """

        from gamification.services.achievements import _is_eligible

        self.assertTrue(
            _is_eligible(
                code="LOW_CARBON_MONTH",
                user=self.user,
            )
        )

        mock_low_carbon.assert_called_once_with(self.user)

    def test_completed_sustainability_actions_are_counted(self):
        """
        Only completed sustainability recommendations should count
        toward SUSTAINABILITY_ACTION_CHAMPION.
        """

        for index in range(3):
            UserRecommendation.objects.create(
                user=self.user,
                recommendation=self.sustainability_recommendation,
                score=Decimal("80.0000") + index,
                reason=f"Test reason {index}",
                status=UserRecommendation.Status.COMPLETED,
            )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=self.sustainability_recommendation,
            score=Decimal("60.0000"),
            reason="Active recommendation",
            status=UserRecommendation.Status.ACTIVE,
        )

        UserRecommendation.objects.create(
            user=self.user,
            recommendation=self.offset_recommendation,
            score=Decimal("90.0000"),
            reason="Completed offset guidance",
            status=UserRecommendation.Status.COMPLETED,
        )

        from gamification.services.achievements import (
            _completed_sustainability_action_count,
        )

        self.assertEqual(
            _completed_sustainability_action_count(self.user),
            3,
        )

    @patch(
        "gamification.services.achievements._is_eligible",
        return_value=True,
    )
    def test_eligible_achievements_are_awarded(
        self,
        mock_is_eligible,
    ):
        """
        When every active achievement is eligible, all five should be
        awarded.
        """

        result = evaluate_achievements(self.user)

        self.assertEqual(
            len(result.earned),
            len(DEFAULT_ACHIEVEMENTS),
        )

        self.assertEqual(
            len(result.newly_awarded),
            len(DEFAULT_ACHIEVEMENTS),
        )

        self.assertEqual(
            UserAchievement.objects.filter(
                user=self.user,
            ).count(),
            len(DEFAULT_ACHIEVEMENTS),
        )

    @patch(
        "gamification.services.achievements._is_eligible",
        return_value=True,
    )
    def test_repeated_evaluation_does_not_duplicate_achievements(
        self,
        mock_is_eligible,
    ):
        """
        Running evaluation repeatedly must not create duplicate
        UserAchievement records.
        """

        first_result = evaluate_achievements(self.user)
        second_result = evaluate_achievements(self.user)

        self.assertEqual(
            len(first_result.newly_awarded),
            len(DEFAULT_ACHIEVEMENTS),
        )

        self.assertEqual(
            len(second_result.newly_awarded),
            0,
        )

        self.assertEqual(
            UserAchievement.objects.filter(
                user=self.user,
            ).count(),
            len(DEFAULT_ACHIEVEMENTS),
        )

    @patch(
        "gamification.services.achievements._is_eligible",
        return_value=True,
    )
    def test_inactive_achievement_is_not_awarded(
        self,
        mock_is_eligible,
    ):
        """
        An inactive achievement must never be awarded, even if its
        eligibility condition evaluates to True.
        """

        seed_default_achievements()

        achievement = Achievement.objects.get(
            code="FIRST_FOOTPRINT",
        )

        achievement.is_active = False
        achievement.save(update_fields=["is_active"])

        result = evaluate_achievements(self.user)

        self.assertNotIn(
            achievement,
            result.earned,
        )

        self.assertFalse(
            UserAchievement.objects.filter(
                user=self.user,
                achievement=achievement,
            ).exists()
        )

    @patch(
        "gamification.services.achievements._is_eligible",
        side_effect=lambda code, user: (
            code in {
                "FIRST_FOOTPRINT",
                "EMISSION_REDUCER",
            }
        ),
    )
    def test_evaluation_returns_only_newly_eligible_achievements(
        self,
        mock_is_eligible,
    ):
        """
        The result should distinguish all earned achievements from
        achievements awarded during the current evaluation.
        """

        seed_default_achievements()

        existing = Achievement.objects.get(
            code="FIRST_FOOTPRINT",
        )

        UserAchievement.objects.create(
            user=self.user,
            achievement=existing,
        )

        result = evaluate_achievements(self.user)

        earned_codes = {
            achievement.code
            for achievement in result.earned
        }

        newly_awarded_codes = {
            achievement.code
            for achievement in result.newly_awarded
        }

        self.assertEqual(
            earned_codes,
            {
                "FIRST_FOOTPRINT",
                "EMISSION_REDUCER",
            },
        )

        self.assertEqual(
            newly_awarded_codes,
            {
                "EMISSION_REDUCER",
            },
        )