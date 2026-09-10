from unittest.mock import patch

from django.test import TestCase

from accounts.models import CustomUser
from recommendations.services.integration import (
    refresh_user_recommendations,
)


class RecommendationIntegrationTests(TestCase):

    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="integration@example.com",
            full_name="Integration User",
            password="test-password-123",
        )

    @patch(
        "recommendations.services.integration."
        "generate_offset_recommendations"
    )
    @patch(
        "recommendations.services.integration."
        "generate_user_recommendations"
    )
    def test_both_recommendation_systems_are_called(
        self,
        generate_user_recommendations,
        generate_offset_recommendations,
    ):
        result = refresh_user_recommendations(
            self.user
        )

        self.assertTrue(result)

        generate_user_recommendations.assert_called_once_with(
            self.user
        )

        generate_offset_recommendations.assert_called_once_with(
            self.user
        )

    @patch(
        "recommendations.services.integration."
        "generate_offset_recommendations"
    )
    @patch(
        "recommendations.services.integration."
        "generate_user_recommendations",
        side_effect=RuntimeError("generic failure"),
    )
    def test_offset_generation_still_runs_when_generic_fails(
        self,
        generate_user_recommendations,
        generate_offset_recommendations,
    ):
        result = refresh_user_recommendations(
            self.user
        )

        self.assertFalse(result)

        generate_user_recommendations.assert_called_once_with(
            self.user
        )

        generate_offset_recommendations.assert_called_once_with(
            self.user
        )

    @patch(
        "recommendations.services.integration."
        "generate_offset_recommendations",
        side_effect=RuntimeError("offset failure"),
    )
    @patch(
        "recommendations.services.integration."
        "generate_user_recommendations"
    )
    def test_generic_generation_succeeds_when_offset_fails(
        self,
        generate_user_recommendations,
        generate_offset_recommendations,
    ):
        result = refresh_user_recommendations(
            self.user
        )

        self.assertFalse(result)

        generate_user_recommendations.assert_called_once_with(
            self.user
        )

        generate_offset_recommendations.assert_called_once_with(
            self.user
        )

    @patch(
        "recommendations.services.integration."
        "generate_offset_recommendations",
        side_effect=Exception("unexpected offset failure"),
    )
    @patch(
        "recommendations.services.integration."
        "generate_user_recommendations",
        side_effect=Exception("unexpected generic failure"),
    )
    def test_unexpected_failures_do_not_escape(
        self,
        generate_user_recommendations,
        generate_offset_recommendations,
    ):
        result = refresh_user_recommendations(
            self.user
        )

        self.assertFalse(result)