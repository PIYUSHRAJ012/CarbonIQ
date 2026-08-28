from carbon.services.emission_import.food import (
    IndiaFoodSourceAdapter,
)
from carbon.services.emission_import.fuel import (
    IndiaFuelSourceAdapter,
)
from carbon.services.emission_import.shopping import (
    IndiaShoppingSourceAdapter,
)
from carbon.services.emission_import.transport import (
    IndiaTransportSourceAdapter,
)
from carbon.services.emission_import.waste import (
    IndiaWasteSourceAdapter,
)


STATIC_SOURCE_ADAPTERS = (
    IndiaTransportSourceAdapter,
    IndiaFuelSourceAdapter,
    IndiaFoodSourceAdapter,
    IndiaShoppingSourceAdapter,
    IndiaWasteSourceAdapter,
)