from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

BENCHMARK_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "mmc2.csv"
)

CENSUS_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "2011-IndiaStateDistSbDistTwn-0000.xlsx"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "processed"
)

OUTPUT_FILE = (
    OUTPUT_DIR
    / "final_benchmark_dataset.csv"
)

UNRESOLVED_FILE = (
    OUTPUT_DIR
    / "final_unresolved_benchmarks.csv"
)


# ---------------------------------------------------------------------
# Validation configuration
# ---------------------------------------------------------------------

# The benchmark values are derived from the same historical source
# population basis, so an effectively exact population match is a
# strong validation signal.
POPULATION_MATCH_TOLERANCE_PERCENT = 0.01


# ---------------------------------------------------------------------
# Historical aliases
# ---------------------------------------------------------------------
#
# These are source-name -> Census-2011-name transformations.
#
# They are NOT accepted blindly. The population fingerprint is still
# validated after applying the alias.
# ---------------------------------------------------------------------

HISTORICAL_ALIASES = {
    # Jammu & Kashmir
    "Leh (Ladakh)": "Leh(Ladakh)",
    "Rajauri": "Rajouri",

    # Punjab
    "Nawanshahr": "Shahid Bhagat Singh Nagar",
    "SJAS Nagar (Mohali)": "Sahibzada Ajit Singh Nagar",

    # Uttar Pradesh
    "Bulandshahar": "Bulandshahr",
    "Hathras": "Mahamaya Nagar",
    "Barabanki": "Bara Banki",
    "Kashiramnagar": "Kanshiram Nagar",

    # Arunachal Pradesh
    "Kurungkumey": "Kurung Kumey",

    # Manipur
    "Senapati (Excluding 3 Sub-Divisions)": "Senapati",

    # Meghalaya
    "Ri Bhoi": "Ribhoi",

    # Assam
    "Marigaon": "Morigaon",
    "Sibsagar": "Sivasagar",
    "North Cachar Hills": "Dima Hasao",
    "Chirag": "Chirang",
    "Guwahati": "Kamrup Metropolitan",

    # West Bengal
    "Pashim Midnapur": "Paschim Medinipur",
    "Purba Midnapur": "Purba Medinipur",

    # Jharkhand
    "Pakaur": "Pakur",
    "Seraikela-kharsawan": "Saraikela-Kharsawan",

    # Odisha
    "Sonapur": "Subarnapur",

    # Chhattisgarh
    "Janjgir-Champa": "Janjgir - Champa",
    "Kawardha": "Kabeerdham",
    "Kanker": "Uttar Bastar Kanker",
    "Dantewada": "Dakshin Bastar Dantewada",

    # Madhya Pradesh
    "West Nimar": "Khargone (West Nimar)",
    "East Nimar": "Khandwa (East Nimar)",

    # Andhra Pradesh
    "Hyderabad and Rangar": "Hyderabad",
    "Rangareddi": "Rangareddy",
    "Nellore": "Sri Potti Sriramulu Nellore",
    "Cuddapah": "Y.S.R.",

    # Karnataka
    "Bijapur (Karnataka)": "Bijapur",
    "Ramanagar": "Ramanagara",

    # Puducherry
    "Pondicherry": "Puducherry",

    # Andaman & Nicobar Islands
    "South Andamans": "South Andaman",
    "North & middle Andamans": "North & Middle Andaman",
}


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def normalize_name(value: object) -> str:
    """
    Normalize a district name for conservative comparison.

    This is intentionally deterministic and does not perform fuzzy
    matching.
    """

    if pd.isna(value):
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("&", " and ")
        .replace("-", " ")
        .replace("'", "")
        .replace(".", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
        .replace("/", " ")
    )


def population_difference_percent(
    census_population: float,
    implied_population: float,
) -> float:
    """
    Calculate absolute percentage difference between Census population
    and benchmark-implied population.
    """

    if implied_population <= 0:
        return float("inf")

    return (
        abs(census_population - implied_population)
        / implied_population
        * 100
    )


# ---------------------------------------------------------------------
# Census preparation
# ---------------------------------------------------------------------

def load_census_districts() -> pd.DataFrame:
    """
    Load the 2011 Census district-total records and attach state names.
    """

    census = pd.read_excel(
        CENSUS_FILE,
        sheet_name="Data",
    )

    # ---------------------------------------------------------------
    # State-level records
    # ---------------------------------------------------------------

    state_rows = census[
        (census["Level"] == "STATE")
        & (census["District"] == 0)
        & (census["Subdistt"] == 0)
        & (census["Town/Village"] == 0)
        & (census["Ward"] == 0)
        & (census["EB"] == 0)
        & (census["TRU"] == "Total")
    ][
        [
            "State",
            "Name",
        ]
    ].copy()

    state_rows = state_rows.rename(
        columns={
            "State": "state_code",
            "Name": "state_name",
        }
    )

    state_rows = state_rows.drop_duplicates(
        subset=["state_code"]
    )

    # ---------------------------------------------------------------
    # District TOTAL records
    # ---------------------------------------------------------------

    district_rows = census[
        (census["Level"] == "DISTRICT")
        & (census["TRU"] == "Total")
        & (census["Subdistt"] == 0)
        & (census["Town/Village"] == 0)
        & (census["Ward"] == 0)
        & (census["EB"] == 0)
        & (census["District"] > 0)
    ].copy()

    district_rows = district_rows[
        [
            "State",
            "District",
            "Name",
            "TOT_P",
        ]
    ].rename(
        columns={
            "State": "state_code",
            "District": "district_code",
            "Name": "census_name",
            "TOT_P": "census_population",
        }
    )

    # Remove " Total" suffix.
    district_rows["census_name"] = (
        district_rows["census_name"]
        .astype(str)
        .str.replace(
            r"\s+Total$",
            "",
            regex=True,
        )
        .str.strip()
    )

    district_rows["normalized_name"] = (
        district_rows["census_name"]
        .map(normalize_name)
    )

    district_rows = district_rows.merge(
        state_rows,
        on="state_code",
        how="left",
        validate="many_to_one",
    )

    # Ensure we have exactly one district record per
    # state_code + district_code.
    duplicate_geographic_keys = district_rows[
        district_rows.duplicated(
            ["state_code", "district_code"],
            keep=False,
        )
    ]

    if not duplicate_geographic_keys.empty:
        raise ValueError(
            "Duplicate Census district geographic keys found."
        )

    if len(district_rows) != 640:
        raise ValueError(
            "Unexpected Census district count: "
            f"{len(district_rows)}. Expected 640."
        )

    return district_rows


# ---------------------------------------------------------------------
# Benchmark preparation
# ---------------------------------------------------------------------

def load_benchmark() -> pd.DataFrame:
    """
    Load and validate the original research benchmark data.
    """

    benchmark = pd.read_csv(
        BENCHMARK_FILE,
    )

    required_columns = {
        "District",
        "CF per capita",
        " Overall CF ",
        "Population density",
        "Poverty ratio",
    }

    missing_columns = (
        required_columns
        - set(benchmark.columns)
    )

    if missing_columns:
        raise ValueError(
            "Benchmark CSV is missing required columns: "
            f"{sorted(missing_columns)}"
        )

    if len(benchmark) != 623:
        raise ValueError(
            "Unexpected benchmark record count: "
            f"{len(benchmark)}. Expected 623."
        )

    benchmark["benchmark_row"] = benchmark.index

    benchmark["original_district"] = (
        benchmark["District"]
        .astype(str)
        .str.strip()
    )

    benchmark["cf_per_capita"] = pd.to_numeric(
        benchmark["CF per capita"],
        errors="coerce",
    )

    benchmark["overall_cf"] = pd.to_numeric(
        benchmark[" Overall CF "],
        errors="coerce",
    )

    if benchmark["cf_per_capita"].isna().any():
        raise ValueError(
            "Invalid CF per capita values found."
        )

    if benchmark["overall_cf"].isna().any():
        raise ValueError(
            "Invalid Overall CF values found."
        )

    if (benchmark["cf_per_capita"] <= 0).any():
        raise ValueError(
            "CF per capita must be greater than zero."
        )

    if (benchmark["overall_cf"] < 0).any():
        raise ValueError(
            "Overall CF cannot be negative."
        )

    benchmark["implied_population"] = (
        benchmark["overall_cf"]
        / benchmark["cf_per_capita"]
    )

    benchmark["canonical_lookup_name"] = (
        benchmark["original_district"]
        .map(
            lambda value: HISTORICAL_ALIASES.get(
                value,
                value,
            )
        )
        .map(normalize_name)
    )

    return benchmark


# ---------------------------------------------------------------------
# Candidate validation
# ---------------------------------------------------------------------

def find_best_population_candidate(
    district_rows: pd.DataFrame,
    implied_population: float,
    candidates: pd.DataFrame | None = None,
):
    """
    Find the best population candidate.

    Population must match within the configured tolerance and must
    clearly beat the second-best candidate.
    """

    if implied_population <= 0:
        return None

    if candidates is None:
        candidates = district_rows.copy()
    else:
        candidates = candidates.copy()

    if candidates.empty:
        return None

    candidates["population_difference_percent"] = (
        (
            candidates["census_population"]
            - implied_population
        ).abs()
        / implied_population
        * 100
    )

    candidates = candidates.sort_values(
        "population_difference_percent"
    ).reset_index(drop=True)

    best = candidates.iloc[0]

    best_difference = float(
        best["population_difference_percent"]
    )

    if best_difference > POPULATION_MATCH_TOLERANCE_PERCENT:
        return None

    if len(candidates) > 1:
        second_difference = float(
            candidates.iloc[1][
                "population_difference_percent"
            ]
        )

        # Don't accept ties or effectively tied candidates.
        if (
            abs(
                second_difference
                - best_difference
            )
            <= 0.000001
        ):
            return None

    return best


# ---------------------------------------------------------------------
# Main resolution
# ---------------------------------------------------------------------

def resolve_benchmark_records(
    benchmark: pd.DataFrame,
    district_rows: pd.DataFrame,
) -> tuple[list[dict], list[dict]]:
    """
    Resolve every benchmark row against historical Census geography.

    Priority:

    1. Exact/alias textual candidate + population validation
    2. Global population fingerprint validation
    3. Otherwise unresolved
    """

    final_rows = []
    unresolved_rows = []

    for _, row in benchmark.iterrows():

        benchmark_name = row["original_district"]
        lookup_name = row["canonical_lookup_name"]

        implied_population = float(
            row["implied_population"]
        )

        # -------------------------------------------------------------
        # Find exact normalized / alias candidates.
        # -------------------------------------------------------------

        text_candidates = district_rows[
            district_rows["normalized_name"]
            == lookup_name
        ].copy()

        selected = None
        mapping_method = None

        # -------------------------------------------------------------
        # IMPORTANT:
        #
        # Even if there is exactly ONE textual candidate,
        # population must still validate it.
        #
        # This prevents:
        #     "North" → Delhi North
        #     "East"  → Delhi East
        # etc.
        # -------------------------------------------------------------

        if not text_candidates.empty:

            selected = find_best_population_candidate(
                district_rows=district_rows,
                implied_population=implied_population,
                candidates=text_candidates,
            )

            if selected is not None:

                if benchmark_name in HISTORICAL_ALIASES:
                    mapping_method = "HISTORICAL_ALIAS"

                elif (
                    len(text_candidates) > 1
                ):
                    mapping_method = (
                        "POPULATION_VALIDATED"
                    )

                else:
                    mapping_method = "EXACT_CENSUS"

        # -------------------------------------------------------------
        # If textual mapping failed, use global population fingerprint.
        # -------------------------------------------------------------

        if selected is None:

            selected = find_best_population_candidate(
                district_rows=district_rows,
                implied_population=implied_population,
                candidates=None,
            )

            if selected is not None:
                mapping_method = "POPULATION_VALIDATED"

        # -------------------------------------------------------------
        # Record successful mapping.
        # -------------------------------------------------------------

        if selected is not None:

            census_population = float(
                selected["census_population"]
            )

            difference_percent = (
                population_difference_percent(
                    census_population,
                    implied_population,
                )
            )

            final_rows.append(
                {
                    "benchmark_row": int(
                        row["benchmark_row"]
                    ),
                    "original_district": benchmark_name,
                    "canonical_district": selected[
                        "census_name"
                    ],
                    "state": selected[
                        "state_name"
                    ],
                    "state_code": int(
                        selected["state_code"]
                    ),
                    "district_code": int(
                        selected["district_code"]
                    ),
                    "cf_per_capita": float(
                        row["cf_per_capita"]
                    ),
                    "overall_cf": float(
                        row["overall_cf"]
                    ),
                    "population_density": float(
                        row["Population density"]
                    ),
                    "poverty_ratio": float(
                        row["Poverty ratio"]
                    ),
                    "implied_population": round(
                        implied_population,
                        2,
                    ),
                    "census_population": int(
                        census_population
                    ),
                    "population_difference_percent": round(
                        difference_percent,
                        6,
                    ),
                    "mapping_method": mapping_method,
                    "reference_period": "2011-2012",
                    "unit": "tCO2/person/year",
                    "population_basis": "per_capita",
                    "source": (
                        "Lee et al. (2021) — "
                        "The scale and drivers "
                        "of carbon footprints in "
                        "households, cities and "
                        "regions across India"
                    ),
                    "source_reference": (
                        "https://doi.org/10.1016/"
                        "j.gloenvcha.2020.102205"
                    ),
                }
            )

        else:

            unresolved_rows.append(
                {
                    "benchmark_row": int(
                        row["benchmark_row"]
                    ),
                    "original_district": benchmark_name,
                    "cf_per_capita": float(
                        row["cf_per_capita"]
                    ),
                    "overall_cf": float(
                        row["overall_cf"]
                    ),
                    "implied_population": round(
                        implied_population,
                        2,
                    ),
                    "lookup_name": lookup_name,
                }
            )

    return final_rows, unresolved_rows


# ---------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------

def main() -> None:

    print("=" * 70)
    print("BUILD FINAL VALIDATED BENCHMARK DATASET")
    print("=" * 70)

    # ---------------------------------------------------------------
    # Validate source files
    # ---------------------------------------------------------------

    for path in (
        BENCHMARK_FILE,
        CENSUS_FILE,
    ):
        if not path.exists():
            raise FileNotFoundError(
                f"Required file not found: {path}"
            )

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    # ---------------------------------------------------------------
    # Load data
    # ---------------------------------------------------------------

    print("\nLoading benchmark dataset...")
    benchmark = load_benchmark()

    print(
        f"Benchmark records: {len(benchmark)}"
    )

    print("\nLoading Census 2011 districts...")
    district_rows = load_census_districts()

    print(
        f"Census district records: "
        f"{len(district_rows)}"
    )

    # ---------------------------------------------------------------
    # Resolve records
    # ---------------------------------------------------------------

    print("\nResolving historical geography...")

    final_rows, unresolved_rows = (
        resolve_benchmark_records(
            benchmark=benchmark,
            district_rows=district_rows,
        )
    )

    final_df = pd.DataFrame(
        final_rows
    )

    unresolved_df = pd.DataFrame(
        unresolved_rows
    )

    # ---------------------------------------------------------------
    # Validate completeness
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("VALIDATION SUMMARY")
    print("=" * 70)

    print(
        f"Original benchmark records : "
        f"{len(benchmark)}"
    )

    print(
        f"Resolved records           : "
        f"{len(final_df)}"
    )

    print(
        f"Unresolved records         : "
        f"{len(unresolved_df)}"
    )

    if len(benchmark) > 0:
        print(
            f"Resolution rate            : "
            f"{len(final_df) / len(benchmark) * 100:.2f}%"
        )

    # ---------------------------------------------------------------
    # Ensure every source row resolved at most once
    # ---------------------------------------------------------------

    if not final_df.empty:

        duplicate_source_rows = (
            final_df[
                "benchmark_row"
            ]
            .duplicated()
            .sum()
        )

        if duplicate_source_rows:
            raise ValueError(
                "Duplicate source benchmark rows found: "
                f"{duplicate_source_rows}"
            )

    # Every benchmark record MUST resolve before import.
    if not unresolved_df.empty:

        unresolved_df.to_csv(
            UNRESOLVED_FILE,
            index=False,
        )

        print(
            "\nUnresolved records were saved to:"
        )

        print(UNRESOLVED_FILE)

        print("\nUnresolved benchmark records:")

        print(
            unresolved_df[
                [
                    "benchmark_row",
                    "original_district",
                    "implied_population",
                ]
            ].to_string(
                index=False
            )
        )

        raise ValueError(
            "Benchmark validation stopped because "
            f"{len(unresolved_df)} records remain unresolved."
        )

    # ---------------------------------------------------------------
    # Ensure all 623 source records resolved
    # ---------------------------------------------------------------

    if len(final_df) != len(benchmark):
        raise ValueError(
            "Final dataset record count does not match "
            "the source benchmark record count."
        )

    # ---------------------------------------------------------------
    # Check logical benchmark identity
    # ---------------------------------------------------------------

    logical_keys = [
        "state",
        "canonical_district",
        "reference_period",
        "source",
    ]

    duplicates = final_df[
        final_df.duplicated(
            logical_keys,
            keep=False,
        )
    ].sort_values(
        logical_keys
    )

    if not duplicates.empty:

        duplicate_file = (
            OUTPUT_DIR
            / "final_logical_duplicates.csv"
        )

        duplicates.to_csv(
            duplicate_file,
            index=False,
        )

        print(
            "\nLogical duplicate benchmark identities found:"
        )

        print(
            duplicates[
                [
                    "benchmark_row",
                    "original_district",
                    "canonical_district",
                    "state",
                    "reference_period",
                ]
            ].to_string(
                index=False
            )
        )

        print(
            f"\nDuplicate report: {duplicate_file}"
        )

        raise ValueError(
            "Final benchmark dataset contains duplicate "
            "geographic benchmark identities."
        )

    # ---------------------------------------------------------------
    # Mapping-method report
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("MAPPING METHODS")
    print("=" * 70)

    print(
        final_df[
            "mapping_method"
        ].value_counts().to_string()
    )

    # ---------------------------------------------------------------
    # State coverage
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("GEOGRAPHIC COVERAGE")
    print("=" * 70)

    print(
        f"Unique states represented: "
        f"{final_df['state'].nunique()}"
    )

    # ---------------------------------------------------------------
    # Save final dataset
    # ---------------------------------------------------------------

    final_df = final_df.sort_values(
        "benchmark_row"
    ).reset_index(
        drop=True
    )

    final_df.to_csv(
        OUTPUT_FILE,
        index=False,
    )

    # ---------------------------------------------------------------
    # Final success message
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("SUCCESS")
    print("=" * 70)

    print(
        f"Final validated benchmark records: "
        f"{len(final_df)}"
    )

    print(
        f"Output: {OUTPUT_FILE}"
    )


if __name__ == "__main__":
    main()