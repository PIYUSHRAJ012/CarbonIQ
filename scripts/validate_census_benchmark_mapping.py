from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CENSUS_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "PC11_TV_DIR.xlsx"
)

BENCHMARK_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "mmc2.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "processed"
)


def normalize_name(value: object) -> str:
    """Conservative normalization for historical district names."""
    if pd.isna(value):
        return ""

    return (
        str(value)
        .strip()
        .lower()
        .replace("&", "and")
        .replace("-", " ")
        .replace("'", "")
        .replace(".", "")
        .replace(",", "")
        .replace("(", "")
        .replace(")", "")
    )


def main() -> None:
    if not CENSUS_FILE.exists():
        raise FileNotFoundError(
            f"Census file not found: {CENSUS_FILE}"
        )

    if not BENCHMARK_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: {BENCHMARK_FILE}"
        )

    census = pd.read_excel(
        CENSUS_FILE,
        sheet_name="Sheet1",
    )

    benchmark = pd.read_csv(BENCHMARK_FILE)

    # ---------------------------------------------------------------
    # Extract historical district-level Census records
    # ---------------------------------------------------------------

    states = (
        census[
            (census["District Code"] == 0)
            & (census["Sub District Code"] == 0)
            & (census["Town-Village Code"] == 0)
        ][
            [
                "State Code",
                "Town-Village Name",
            ]
        ]
        .rename(
            columns={
                "Town-Village Name": "state_name"
            }
        )
    )

    districts = (
        census[
            (census["District Code"] > 0)
            & (census["Sub District Code"] == 0)
            & (census["Town-Village Code"] == 0)
        ][
            [
                "State Code",
                "District Code",
                "Town-Village Name",
            ]
        ]
        .rename(
            columns={
                "Town-Village Name": "district_name"
            }
        )
    )

    historical = districts.merge(
        states,
        on="State Code",
        how="left",
    )

    # ---------------------------------------------------------------
    # Normalize names
    # ---------------------------------------------------------------

    benchmark["benchmark_district_normalized"] = (
        benchmark["District"].map(normalize_name)
    )

    historical["census_district_normalized"] = (
        historical["district_name"].map(normalize_name)
    )

    # ---------------------------------------------------------------
    # Detect duplicate Census normalized names
    # ---------------------------------------------------------------

    duplicate_census = historical[
        historical["census_district_normalized"]
        .duplicated(keep=False)
    ].sort_values(
        "census_district_normalized"
    )

    # Only use uniquely identifiable district names
    historical_unique = historical[
        ~historical["census_district_normalized"]
        .duplicated(keep=False)
    ].copy()

    # ---------------------------------------------------------------
    # Match benchmark → historical Census district
    # ---------------------------------------------------------------

    merged = benchmark.merge(
        historical_unique[
            [
                "census_district_normalized",
                "state_name",
                "District Code",
                "district_name",
            ]
        ],
        left_on="benchmark_district_normalized",
        right_on="census_district_normalized",
        how="left",
        indicator=True,
    )

    matched = merged[
        merged["_merge"] == "both"
    ].copy()

    unmatched = merged[
        merged["_merge"] == "left_only"
    ].copy()

    # ---------------------------------------------------------------
    # Statistics
    # ---------------------------------------------------------------

    total = len(benchmark)
    matched_count = len(matched)
    unmatched_count = len(unmatched)

    match_rate = (
        matched_count / total * 100
        if total
        else 0
    )

    print("=" * 70)
    print("CENSUS 2011 HISTORICAL DISTRICT MAPPING")
    print("=" * 70)

    print(f"Benchmark rows: {total}")
    print(f"Census district rows: {len(historical)}")
    print(
        "Unique Census normalized district names: "
        f"{historical_unique['census_district_normalized'].nunique()}"
    )

    print()
    print(f"Exact normalized matches: {matched_count}")
    print(f"Unmatched: {unmatched_count}")
    print(f"Match rate: {match_rate:.2f}%")

    # ---------------------------------------------------------------
    # Unmatched districts
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("UNMATCHED BENCHMARK DISTRICTS")
    print("=" * 70)

    if unmatched.empty:
        print("None")
    else:
        for district in unmatched["District"].tolist():
            print(district)

    # ---------------------------------------------------------------
    # Output files
    # ---------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    matched.to_csv(
        OUTPUT_DIR / "census_exact_matches.csv",
        index=False,
    )

    unmatched.to_csv(
        OUTPUT_DIR / "census_unmatched.csv",
        index=False,
    )

    duplicate_census.to_csv(
        OUTPUT_DIR / "census_duplicate_names.csv",
        index=False,
    )

    print("\n" + "=" * 70)
    print("OUTPUT FILES")
    print("=" * 70)

    print(
        OUTPUT_DIR
        / "census_exact_matches.csv"
    )

    print(
        OUTPUT_DIR
        / "census_unmatched.csv"
    )

    print(
        OUTPUT_DIR
        / "census_duplicate_names.csv"
    )


if __name__ == "__main__":
    main()