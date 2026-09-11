from datetime import datetime
from unittest.mock import MagicMock, patch

import numpy as np

from django.test import TestCase
from django.utils import timezone

from accounts.models import CustomUser
from carbon.models import (
    ActivityCategory,
    ActivityEntry,
    CarbonActivity,
    CarbonFootprint,
    EmissionFactor,
)
from ml.services.prediction import predict_next_month_carbon


class PredictionServiceTests(TestCase):
    def setUp(self):
        self.user = CustomUser.objects.create_user(
            email="prediction@example.com",
            full_name="Prediction User",
            password="TestPassword123!",
        )

        self.electricity = ActivityCategory.objects.create(
            name="Electricity",
            description="Electricity consumption",
            unit="kWh",
            display_order=1,
            is_active=True,
        )

        self.diesel = ActivityCategory.objects.create(
            name="Diesel",
            description="Diesel consumption",
            unit="litre",
            display_order=2,
            is_active=True,
        )

        self.electricity_factor = EmissionFactor.objects.create(
            activity_category=self.electricity,
            factor="0.700000",
            source="Test source",
            effective_from=datetime(2026, 1, 1).date(),
            is_active=True,
        )

        self.activity = CarbonActivity.objects.create(
            user=self.user,
            status=CarbonActivity.Status.COMPLETED,
        )

        activity_date = timezone.make_aware(
            datetime(2026, 9, 15, 12, 0)
        )

        CarbonActivity.objects.filter(
            pk=self.activity.pk
        ).update(
            created_at=activity_date
        )

        self.activity.refresh_from_db()

        ActivityEntry.objects.create(
            carbon_activity=self.activity,
            category=self.electricity,
            emission_factor=self.electricity_factor,
            quantity="100.00",
            emission_factor_snapshot="0.7000",
            entry_emission="70.0000",
        )

        CarbonFootprint.objects.create(
            carbon_activity=self.activity,
            total_emission="70.0000",
            calculation_version="v1.0",
        )

    @patch("ml.services.prediction.load_random_forest_metadata")
    @patch("ml.services.prediction.load_random_forest_model")
    def test_prediction_uses_canonical_active_category_schema(
        self,
        mock_load_model,
        mock_load_metadata,
    ):
        model = MagicMock()
        model.n_features_in_ = 4
        model.predict.return_value = np.array([80.0])

        mock_load_model.return_value = model

        mock_load_metadata.return_value = {
            "model_version": "rf-temporal-v1",
            "prediction_type": "next_month_carbon_footprint",
            "feature_names": [
                "previous_diesel",
                "previous_electricity",
                "previous_submission_count",
                "previous_total_emission",
            ],
        }

        result = predict_next_month_carbon(
            self.user.id
        )

        self.assertEqual(
            result.predicted_emission,
            80.0,
        )

        self.assertEqual(
            result.feature_period.year,
            2026,
        )

        self.assertEqual(
            result.feature_period.month,
            9,
        )

        model.predict.assert_called_once()

        prediction_features = model.predict.call_args[0][0]

        self.assertEqual(
            list(prediction_features.columns),
            [
                "previous_diesel",
                "previous_electricity",
                "previous_submission_count",
                "previous_total_emission",
            ],
        )

        self.assertEqual(
            prediction_features.iloc[0]["previous_diesel"],
            0.0,
        )