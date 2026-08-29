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


MODEL_VERSION = "rf-v1"
TARGET_NAME = "total_emission"


class Command(BaseCommand):
    """
    Train the CarbonIQ Random Forest carbon-footprint prediction model.
    """

    help = (
        "Train the Random Forest carbon-footprint prediction model "
        "using completed CarbonIQ submissions."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Preparing Random Forest training dataset..."
            )
        )

        try:
            result = train_random_forest_from_database()

            metadata = {
                "model_version": MODEL_VERSION,
                "target": TARGET_NAME,
                "features": list(result.feature_names),
                "sample_count": result.sample_count,
                "training_samples": result.training_samples,
                "test_samples": result.test_samples,
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