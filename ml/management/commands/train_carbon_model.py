from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from ml.services.feature_engineering import MLDataError
from ml.services.model_persistence import (
    ModelPersistenceError,
    save_random_forest_model,
)
from ml.training.random_forest import (
    train_random_forest_from_database,
)


logger = logging.getLogger(__name__)


MODEL_VERSION = "rf-temporal-v1"
TARGET_NAME = "next_total_emission"


class Command(BaseCommand):
    """
    Train the CarbonIQ temporal Random Forest carbon-footprint
    prediction model.
    """

    help = (
        "Train the temporal Random Forest carbon-footprint "
        "prediction model using completed CarbonIQ submissions."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Preparing Random Forest temporal training dataset..."
            )
        )

        try:
            result = train_random_forest_from_database()

            metadata = {
                "model_version": MODEL_VERSION,
                "prediction_type": "next_month_carbon_footprint",
                "target": TARGET_NAME,
                "features": list(result.feature_names),
                "sample_count": result.sample_count,
                "training_samples": result.training_samples,
                "test_samples": result.test_samples,
                "user_count": result.user_count,
                "training_period_start": result.training_period_start,
                "training_period_end": result.training_period_end,
                "test_period_start": result.test_period_start,
                "test_period_end": result.test_period_end,
                "mae": result.mae,
                "rmse": result.rmse,
                "r2": result.r2,
            }

            model_path, metadata_path = save_random_forest_model(
                model=result.model,
                metadata=metadata,
            )

        except MLDataError as exc:
            logger.warning(
                "Random Forest training data error: %s",
                exc,
            )

            raise CommandError(str(exc)) from exc

        except ModelPersistenceError as exc:
            logger.error(
                "Random Forest model persistence error: %s",
                exc,
            )

            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "Random Forest training completed successfully."
            )
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                f"Samples: {result.sample_count}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Users: {result.user_count}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Training samples: {result.training_samples}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Test samples: {result.test_samples}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Features: {len(result.feature_names)}"
            )
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                "Training target period:"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"  {result.training_period_start}"
                f" → "
                f"{result.training_period_end}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                "Test target period:"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"  {result.test_period_start}"
                f" → "
                f"{result.test_period_end}"
            )
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                f"MAE : {result.mae:.4f}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"RMSE: {result.rmse:.4f}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"R²  : {result.r2:.4f}"
            )
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                f"Model saved: {model_path}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Metadata saved: {metadata_path}"
            )
        )