from django.test import SimpleTestCase

from carbon.services.emission_import.sources import (
    STATIC_SOURCE_ADAPTERS,
)


class EmissionSourceRegistryTests(SimpleTestCase):
    """
    Tests for the emission-factor source registry.
    """

    def test_registry_contains_expected_source_adapters(self):
        adapter_names = {
            adapter.__name__
            for adapter in STATIC_SOURCE_ADAPTERS
        }

        self.assertEqual(
            adapter_names,
            {
                "IndiaTransportSourceAdapter",
                "IndiaFuelSourceAdapter",
                "IndiaFoodSourceAdapter",
                "IndiaShoppingSourceAdapter",
                "IndiaWasteSourceAdapter",
            },
        )

    def test_registered_adapters_expose_common_interface(self):
        for adapter in STATIC_SOURCE_ADAPTERS:
            self.assertTrue(
                hasattr(adapter, "get_factors")
            )

            factors = adapter.get_factors()

            self.assertIsInstance(
                factors,
                list,
            )

            self.assertGreater(
                len(factors),
                0,
            )