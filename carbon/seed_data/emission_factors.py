from datetime import date


DEFAULT_EMISSION_FACTORS = [
    {
        "category": "Electricity",
        "factor": 0.708,
        "source": "Central Electricity Authority (India)",
        "effective_from": date(2026, 1, 1),
    },
    {
        "category": "Transportation",
        "factor": 0.121,
        "source": "Average passenger transport emission factor",
        "effective_from": date(2026, 1, 1),
    },
    {
        "category": "Food",
        "factor": 2.50,
        "source": "Average mixed diet emission estimate",
        "effective_from": date(2026, 1, 1),
    },
    {
        "category": "Shopping",
        "factor": 0.040,
        "source": "Simplified consumption-based estimate",
        "effective_from": date(2026, 1, 1),
    },
    {
        "category": "Waste",
        "factor": 0.570,
        "source": "Municipal solid waste emission estimate",
        "effective_from": date(2026, 1, 1),
    },
]
