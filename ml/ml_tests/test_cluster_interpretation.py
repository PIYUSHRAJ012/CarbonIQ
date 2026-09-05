from unittest import TestCase

from ml.services.cluster_interpretation import (
    DEFAULT_DOMAINS,
    ClusterInterpretationError,
    calculate_domain_scores,
    interpret_cluster,
    map_feature_to_domain,
)


class FeatureDomainMappingTests(TestCase):
    """Tests for mapping ML features to behavioural domains."""

    def test_electricity_maps_to_energy(self):
        self.assertEqual(
            map_feature_to_domain("electricity"),
            "energy",
        )

    def test_transportation_maps_to_transport(self):
        self.assertEqual(
            map_feature_to_domain("transportation"),
            "transport",
        )

    def test_petrol_maps_to_transport(self):
        self.assertEqual(
            map_feature_to_domain("petrol"),
            "transport",
        )

    def test_diesel_maps_to_transport(self):
        self.assertEqual(
            map_feature_to_domain("diesel"),
            "transport",
        )

    def test_food_features_map_to_food(self):
        self.assertEqual(
            map_feature_to_domain("rice_grain"),
            "food",
        )

        self.assertEqual(
            map_feature_to_domain("milk"),
            "food",
        )

        self.assertEqual(
            map_feature_to_domain("tofu"),
            "food",
        )

    def test_shopping_features_map_to_shopping(self):
        self.assertEqual(
            map_feature_to_domain("clothing"),
            "shopping",
        )

        self.assertEqual(
            map_feature_to_domain("footwear"),
            "shopping",
        )

    def test_waste_maps_to_waste(self):
        self.assertEqual(
            map_feature_to_domain("waste"),
            "waste",
        )

    def test_unknown_feature_returns_none(self):
        self.assertIsNone(
            map_feature_to_domain("unknown_feature"),
        )

    def test_summary_features_are_not_behavioural_domains(self):
        self.assertIsNone(
            map_feature_to_domain(
                "avg_total_emission"
            )
        )

        self.assertIsNone(
            map_feature_to_domain(
                "submission_count"
            )
        )


class DomainScoreTests(TestCase):
    """Tests for calculating domain-level relative strengths."""

    def test_domain_scores_are_calculated(self):
        centroid = {
            "electricity": 400.0,
            "transportation": 100.0,
            "food": 200.0,
            "waste": 20.0,
        }

        population_means = {
            "electricity": 200.0,
            "transportation": 100.0,
            "food": 200.0,
            "waste": 20.0,
        }

        scores = calculate_domain_scores(
            centroid,
            population_means,
        )

        self.assertEqual(
            scores["energy"],
            2.0,
        )

        self.assertEqual(
            scores["transport"],
            1.0,
        )

        self.assertEqual(
            scores["food"],
            1.0,
        )

        self.assertEqual(
            scores["waste"],
            1.0,
        )

    def test_multiple_features_in_same_domain_are_combined(self):
        centroid = {
            "transportation": 200.0,
            "petrol": 100.0,
            "diesel": 100.0,
        }

        population_means = {
            "transportation": 100.0,
            "petrol": 50.0,
            "diesel": 50.0,
        }

        scores = calculate_domain_scores(
            centroid,
            population_means,
        )

        self.assertEqual(
            scores["transport"],
            2.0,
        )

    def test_zero_population_mean_is_handled(self):
        centroid = {
            "electricity": 100.0,
        }

        population_means = {
            "electricity": 0.0,
        }

        scores = calculate_domain_scores(
            centroid,
            population_means,
        )

        self.assertEqual(
            scores["energy"],
            0.0,
        )

    def test_unknown_features_are_ignored(self):
        centroid = {
            "unknown_feature": 100.0,
            "electricity": 200.0,
        }

        population_means = {
            "unknown_feature": 50.0,
            "electricity": 100.0,
        }

        scores = calculate_domain_scores(
            centroid,
            population_means,
        )

        self.assertNotIn(
            "unknown",
            scores,
        )

        self.assertEqual(
            scores["energy"],
            2.0,
        )

    def test_all_default_domains_are_present(self):
        centroid = {
            "electricity": 100.0,
        }

        population_means = {
            "electricity": 100.0,
        }

        scores = calculate_domain_scores(
            centroid,
            population_means,
        )

        for domain in DEFAULT_DOMAINS:
            self.assertIn(
                domain,
                scores,
            )


class ClusterInterpretationTests(TestCase):
    """Tests for generating human-readable cluster profiles."""

    def test_energy_dominant_cluster_is_energy_oriented(self):
        centroid = {
            "electricity": 400.0,
            "transportation": 100.0,
            "food": 100.0,
            "clothing": 100.0,
            "waste": 50.0,
        }

        population_means = {
            "electricity": 200.0,
            "transportation": 100.0,
            "food": 100.0,
            "clothing": 100.0,
            "waste": 50.0,
        }

        result = interpret_cluster(
            cluster_id=0,
            centroid=centroid,
            population_means=population_means,
        )

        self.assertEqual(
            result.cluster_id,
            0,
        )

        self.assertEqual(
            result.dominant_domain,
            "energy",
        )

        self.assertEqual(
            result.profile_name,
            "Energy-oriented",
        )

    def test_transport_dominant_cluster_is_transport_oriented(self):
        centroid = {
            "electricity": 100.0,
            "transportation": 300.0,
            "petrol": 100.0,
            "food": 100.0,
        }

        population_means = {
            "electricity": 100.0,
            "transportation": 100.0,
            "petrol": 100.0,
            "food": 100.0,
        }

        result = interpret_cluster(
            cluster_id=1,
            centroid=centroid,
            population_means=population_means,
        )

        self.assertEqual(
            result.dominant_domain,
            "transport",
        )

        self.assertEqual(
            result.profile_name,
            "Transport-oriented",
        )

    def test_balanced_cluster_is_balanced(self):
        centroid = {
            "electricity": 105.0,
            "transportation": 100.0,
            "food": 103.0,
            "clothing": 98.0,
            "waste": 101.0,
        }

        population_means = {
            "electricity": 100.0,
            "transportation": 100.0,
            "food": 100.0,
            "clothing": 100.0,
            "waste": 100.0,
        }

        result = interpret_cluster(
            cluster_id=2,
            centroid=centroid,
            population_means=population_means,
        )

        self.assertEqual(
            result.dominant_domain,
            "balanced",
        )

        self.assertEqual(
            result.profile_name,
            "Balanced profile",
        )

    def test_cluster_id_does_not_determine_profile(self):
        centroid = {
            "electricity": 400.0,
            "transportation": 100.0,
        }

        population_means = {
            "electricity": 200.0,
            "transportation": 100.0,
        }

        first = interpret_cluster(
            cluster_id=0,
            centroid=centroid,
            population_means=population_means,
        )

        second = interpret_cluster(
            cluster_id=99,
            centroid=centroid,
            population_means=population_means,
        )

        self.assertEqual(
            first.dominant_domain,
            second.dominant_domain,
        )

        self.assertEqual(
            first.profile_name,
            second.profile_name,
        )

    def test_invalid_centroid_feature_value_is_rejected(self):
        centroid = {
            "electricity": "invalid",
        }

        population_means = {
            "electricity": 100.0,
        }

        with self.assertRaises(
            ClusterInterpretationError
        ):
            interpret_cluster(
                cluster_id=0,
                centroid=centroid,
                population_means=population_means,
            )

    def test_missing_population_mean_is_rejected(self):
        centroid = {
            "electricity": 200.0,
        }

        population_means = {}

        with self.assertRaises(
            ClusterInterpretationError
        ):
            interpret_cluster(
                cluster_id=0,
                centroid=centroid,
                population_means=population_means,
            )