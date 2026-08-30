from __future__ import annotations

import logging

from django.core.management.base import BaseCommand, CommandError

from ml.services.feature_engineering import MLDataError
from ml.services.model_persistence import (
    ModelPersistenceError,
    save_kmeans_model,
)
from ml.training.kmeans import train_kmeans_from_database


logger = logging.getLogger(__name__)

MODEL_VERSION = "kmeans-v1"


class Command(BaseCommand):
    """
    Train the CarbonIQ K-Means user segmentation model.
    """

    help = (
        "Train the K-Means user segmentation model "
        "using completed CarbonIQ user history."
    )

    def handle(self, *args, **options):
        self.stdout.write(
            self.style.NOTICE(
                "Preparing K-Means user segmentation dataset..."
            )
        )

        try:
            result = train_kmeans_from_database()

            metadata = {
                "model_version": MODEL_VERSION,
                "model_type": "user_segmentation",
                "features": list(result.feature_names),
                "user_count": result.user_count,
                "selected_k": result.selected_k,
                "candidate_scores": {
                    str(k): score
                    for k, score in result.candidate_scores.items()
                },
                "silhouette_score": result.silhouette_score,
                "cluster_sizes": {
                    str(cluster): size
                    for cluster, size in result.cluster_sizes.items()
                },
            }

            model_path, metadata_path = save_kmeans_model(
                model=result.model,
                scaler=result.scaler,
                metadata=metadata,
            )

        except MLDataError as exc:
            logger.warning(
                "K-Means training data error: %s",
                exc,
            )

            raise CommandError(str(exc)) from exc

        except ModelPersistenceError as exc:
            logger.error(
                "K-Means model persistence error: %s",
                exc,
            )

            raise CommandError(str(exc)) from exc

        self.stdout.write(
            self.style.SUCCESS(
                "K-Means user segmentation training completed successfully."
            )
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                f"Users: {result.user_count}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Features: {len(result.feature_names)}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Selected K: {result.selected_k}"
            )
        )

        self.stdout.write(
            self.style.NOTICE(
                f"Silhouette Score: {result.silhouette_score:.4f}"
            )
        )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                "Candidate K scores:"
            )
        )

        for k, score in sorted(
            result.candidate_scores.items()
        ):
            self.stdout.write(
                self.style.NOTICE(
                    f"  K={k}: {score:.4f}"
                )
            )

        self.stdout.write("")

        self.stdout.write(
            self.style.NOTICE(
                "Cluster sizes:"
            )
        )

        for cluster, size in sorted(
            result.cluster_sizes.items()
        ):
            self.stdout.write(
                self.style.NOTICE(
                    f"  Cluster {cluster}: {size} users"
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