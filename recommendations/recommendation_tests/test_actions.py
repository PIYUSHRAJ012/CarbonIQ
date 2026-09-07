from django.test import TestCase

from accounts.models import CustomUser
from recommendations.models import Recommendation, UserRecommendation
from recommendations.services.actions import (
    RecommendationActionError,
    dismiss_recommendation,
    mark_recommendation_completed,
)

from decimal import Decimal

from gamification.models import Challenge, UserChallenge

class RecommendationActionServiceTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="user1@example.com",
            full_name="Test User One",
            password="test-password-123",
        )

        self.other_user = CustomUser.objects.create_user(
            email="user2@example.com",
            full_name="Test User Two",
            password="test-password-123",
        )

        self.recommendation = Recommendation.objects.create(
            title="Reduce electricity consumption",
            description=(
                "Reduce avoidable electricity consumption."
            ),
            category=None,
            action_type=Recommendation.ActionType.SUSTAINABILITY,
            priority=80,
            applicable_segment="",
            is_active=True,
        )

        self.user_recommendation = UserRecommendation.objects.create(
            user=self.user,
            recommendation=self.recommendation,
            score=75,
            reason=(
                "Electricity contributes significantly "
                "to your footprint."
            ),
            status=UserRecommendation.Status.ACTIVE,
        )

    def test_active_recommendation_can_be_completed(self):
        result = mark_recommendation_completed(
            user=self.user,
            recommendation_id=self.user_recommendation.id,
        )

        self.assertEqual(
            result.status,
            UserRecommendation.Status.COMPLETED,
        )

        self.user_recommendation.refresh_from_db()

        self.assertEqual(
            self.user_recommendation.status,
            UserRecommendation.Status.COMPLETED,
        )

    def test_completing_sustainability_recommendation_updates_active_challenge(self):
        challenge = Challenge.objects.create(
            code="SUSTAINABILITY_ACTION_CHALLENGE",
            title="Complete Sustainability Actions",
            description="Test challenge.",
            metric=Challenge.Metric.SUSTAINABLE_ACTIONS,
            target=Decimal("3"),
            start_date="2026-09-01",
            end_date="2026-12-31",
            is_active=True,
        )

        user_challenge = UserChallenge.objects.create(
            user=self.user,
            challenge=challenge,
        )

        mark_recommendation_completed(
            user=self.user,
            recommendation_id=self.user_recommendation.id,
        )

        user_challenge.refresh_from_db()

        self.assertEqual(
            user_challenge.progress,
            Decimal("1"),
        )

        self.assertFalse(
            user_challenge.completed,
        )

    def test_completing_sustainability_recommendation_evaluates_achievements(self):
        from gamification.models import Achievement, UserAchievement

        achievement = Achievement.objects.create(
            code="SUSTAINABILITY_ACTION_CHAMPION",
            name="Sustainability Action Champion",
            description=(
                "Complete at least three personalized sustainability "
                "recommendations."
            ),
            icon="fa-seedling",
            is_active=True,
        )

        mark_recommendation_completed(
            user=self.user,
            recommendation_id=self.user_recommendation.id,
        )

        self.assertFalse(
            UserAchievement.objects.filter(
                user=self.user,
                achievement=achievement,
            ).exists()
        )

    def test_active_recommendation_can_be_dismissed(self):
        result = dismiss_recommendation(
            user=self.user,
            recommendation_id=self.user_recommendation.id,
        )

        self.assertEqual(
            result.status,
            UserRecommendation.Status.DISMISSED,
        )

        self.user_recommendation.refresh_from_db()

        self.assertEqual(
            self.user_recommendation.status,
            UserRecommendation.Status.DISMISSED,
        )

    def test_other_user_cannot_complete_recommendation(self):
        with self.assertRaises(RecommendationActionError):
            mark_recommendation_completed(
                user=self.other_user,
                recommendation_id=self.user_recommendation.id,
            )

        self.user_recommendation.refresh_from_db()

        self.assertEqual(
            self.user_recommendation.status,
            UserRecommendation.Status.ACTIVE,
        )

    def test_other_user_cannot_dismiss_recommendation(self):
        with self.assertRaises(RecommendationActionError):
            dismiss_recommendation(
                user=self.other_user,
                recommendation_id=self.user_recommendation.id,
            )

        self.user_recommendation.refresh_from_db()

        self.assertEqual(
            self.user_recommendation.status,
            UserRecommendation.Status.ACTIVE,
        )

    def test_completed_recommendation_cannot_be_completed_again(self):
        self.user_recommendation.status = (
            UserRecommendation.Status.COMPLETED
        )
        self.user_recommendation.save(
            update_fields=["status"]
        )

        with self.assertRaises(RecommendationActionError):
            mark_recommendation_completed(
                user=self.user,
                recommendation_id=self.user_recommendation.id,
            )

    def test_completed_recommendation_cannot_be_dismissed(self):
        self.user_recommendation.status = (
            UserRecommendation.Status.COMPLETED
        )
        self.user_recommendation.save(
            update_fields=["status"]
        )

        with self.assertRaises(RecommendationActionError):
            dismiss_recommendation(
                user=self.user,
                recommendation_id=self.user_recommendation.id,
            )

    def test_dismissed_recommendation_cannot_be_completed(self):
        self.user_recommendation.status = (
            UserRecommendation.Status.DISMISSED
        )
        self.user_recommendation.save(
            update_fields=["status"]
        )

        with self.assertRaises(RecommendationActionError):
            mark_recommendation_completed(
                user=self.user,
                recommendation_id=self.user_recommendation.id,
            )

    def test_dismissed_recommendation_cannot_be_dismissed_again(self):
        self.user_recommendation.status = (
            UserRecommendation.Status.DISMISSED
        )
        self.user_recommendation.save(
            update_fields=["status"]
        )

        with self.assertRaises(RecommendationActionError):
            dismiss_recommendation(
                user=self.user,
                recommendation_id=self.user_recommendation.id,
            )

    def test_missing_recommendation_raises_error(self):
        with self.assertRaises(RecommendationActionError):
            mark_recommendation_completed(
                user=self.user,
                recommendation_id=999999,
            )

    def test_dismiss_missing_recommendation_raises_error(self):
        with self.assertRaises(RecommendationActionError):
            dismiss_recommendation(
                user=self.user,
                recommendation_id=999999,
            )