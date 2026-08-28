from datetime import date


DEFAULT_EMISSION_FACTORS = [
    {
    "category": "Electricity",
    "factor": 0.7117,
    "source": "Central Electricity Authority (India) - CO2 Baseline Database",
    "effective_from": date(2024, 4, 1),
    },
    {
        "category": "Transportation",
        "factor": 0.121,
        "source": "Average passenger transport emission factor",
        "effective_from": date(2026, 1, 1),
    },
    {
        "category": "Clothing",
        "factor": 0.0411,
        "source": (
            "India-specific household carbon footprint study - "
            "Readymade Garments"
        ),
        "effective_from": date(2005, 1, 1),
    },
    {
        "category": "Footwear",
        "factor": 0.0268,
        "source": (
            "India-specific household carbon footprint study - "
            "Leather Footwear"
        ),
        "effective_from": date(2005, 1, 1),
    },
    {
        "category": "Waste",
        "factor": 0.570,
        "source": "Municipal solid waste emission estimate",
        "effective_from": date(2026, 1, 1),
    },
    {
        "category": "Petrol",
        "factor": 2.37135,
        "source": (
            "Bureau of Energy Efficiency (India) - "
            "CAFE 2027 fuel consumption/CO2 relationship"
        ),
        "effective_from": date(2026, 4, 1),
    },
    {
        "category": "Diesel",
        "factor": 2.64831,
        "source": (
            "Bureau of Energy Efficiency (India) - "
            "CAFE 2027 fuel consumption/CO2 relationship"
        ),
        "effective_from": date(2026, 4, 1),
    },
    {
        "category": "Rice & Grain",
        "factor": 3.6,
        "source": (
            "NABARD Working Paper 2025-1 - "
            "Emission of Greenhouse Gases Due to Production of Food Items"
        ),
        "effective_from": date(2025, 1, 1),
    },
    {
        "category": "Legumes",
        "factor": 2.0,
        "source": (
            "NABARD Working Paper 2025-1 - "
            "Emission of Greenhouse Gases Due to Production of Food Items"
        ),
        "effective_from": date(2025, 1, 1),
    },
    {
        "category": "Milk",
        "factor": 3.2,
        "source": (
            "NABARD Working Paper 2025-1 - "
            "Emission of Greenhouse Gases Due to Production of Food Items"
        ),
        "effective_from": date(2025, 1, 1),
    },
    {
        "category": "Tofu",
        "factor": 3.2,
        "source": (
            "NABARD Working Paper 2025-1 - "
            "Emission of Greenhouse Gases Due to Production of Food Items"
        ),
        "effective_from": date(2025, 1, 1),
    },
    {
        "category": "Fruit",
        "factor": 0.9,
        "source": (
            "NABARD Working Paper 2025-1 - "
            "Emission of Greenhouse Gases Due to Production of Food Items"
        ),
        "effective_from": date(2025, 1, 1),
    },
    {
        "category": "Vegetables",
        "factor": 0.7,
        "source": (
            "NABARD Working Paper 2025-1 - "
            "Emission of Greenhouse Gases Due to Production of Food Items"
        ),
        "effective_from": date(2025, 1, 1),
    },
]
