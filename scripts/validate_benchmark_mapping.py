from pathlib import Path

import pandas as pd


# ---------------------------------------------------------------------
# Project paths
# ---------------------------------------------------------------------

PROJECT_ROOT = Path(__file__).resolve().parent.parent

LGD_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "lgd_districts.csv"
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


# ---------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------

def normalize_name(value: object) -> str:
    """
    Normalize a district name for conservative exact matching.

    This function does not perform fuzzy matching.
    """

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
    )


# ---------------------------------------------------------------------
# Main validation
# ---------------------------------------------------------------------

def main() -> None:
    # Check source files exist before reading them.
    if not LGD_FILE.exists():
        raise FileNotFoundError(
            f"LGD file not found: {LGD_FILE}"
        )

    if not BENCHMARK_FILE.exists():
        raise FileNotFoundError(
            f"Benchmark file not found: {BENCHMARK_FILE}"
        )

    print("=" * 70)
    print("LOADING SOURCE DATA")
    print("=" * 70)

    lgd = pd.read_csv(LGD_FILE)
    benchmark = pd.read_csv(BENCHMARK_FILE)

    # ---------------------------------------------------------------
    # Normalize district names
    # ---------------------------------------------------------------

    benchmark["district_normalized"] = (
        benchmark["District"]
        .map(normalize_name)
    )

    lgd["district_normalized"] = (
        lgd["district_name_english"]
        .map(normalize_name)
    )

    print(f"LGD rows: {len(lgd)}")
    print(f"Benchmark rows: {len(benchmark)}")

    # ---------------------------------------------------------------
    # Duplicate analysis
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("DUPLICATE ANALYSIS")
    print("=" * 70)

    benchmark_duplicates = (
        benchmark[
            benchmark["district_normalized"]
            .duplicated(keep=False)
        ]
        .sort_values("district_normalized")
    )

    lgd_duplicates = (
        lgd[
            lgd["district_normalized"]
            .duplicated(keep=False)
        ]
        .sort_values("district_normalized")
    )

    benchmark_duplicate_names = (
        benchmark_duplicates["district_normalized"]
        .nunique()
    )

    lgd_duplicate_names = (
        lgd_duplicates["district_normalized"]
        .nunique()
    )

    print(
        "Benchmark duplicate district names: "
        f"{benchmark_duplicate_names}"
    )

    print(
        "LGD duplicate district names: "
        f"{lgd_duplicate_names}"
    )

    # ---------------------------------------------------------------
    # Keep only uniquely identifiable LGD district names
    # ---------------------------------------------------------------

    lgd_unique = lgd[
        ~lgd["district_normalized"].duplicated(keep=False)
    ].copy()

    # ---------------------------------------------------------------
    # Exact normalized matching
    # ---------------------------------------------------------------

    print("\n" + "=" * 70)
    print("EXACT NORMALIZED MATCH")
    print("=" * 70)

    merged = benchmark.merge(
        lgd_unique[
            [
                "district_normalized",
                "state_name_english",
                "district_name_english",
                "state_code",
                "district_code",
                "state_census2011_code",
                "district_census2011_code",
            ]
        ],
        on="district_normalized",
        how="left",
        indicator=True,
    )

    exact_matches = merged[
        merged["_merge"] == "both"
    ].copy()

    unmatched = merged[
        merged["_merge"] == "left_only"
    ].copy()

    match_rate = (
        len(exact_matches) / len(benchmark) * 100
        if len(benchmark) > 0
        else 0
    )

    print(f"Exact matches: {len(exact_matches)}")
    print(f"Unmatched: {len(unmatched)}")
    print(f"Match rate: {match_rate:.2f}%")

    # ---------------------------------------------------------------
    # Show unmatched districts
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
    # Save validation outputs
    # ---------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    exact_matches_file = (
        OUTPUT_DIR / "exact_matches.csv"
    )

    unmatched_file = (
        OUTPUT_DIR / "unmatched.csv"
    )

    benchmark_duplicates_file = (
        OUTPUT_DIR / "benchmark_duplicates.csv"
    )

    lgd_duplicates_file = (
        OUTPUT_DIR / "lgd_duplicates.csv"
    )

    exact_matches.to_csv(
        exact_matches_file,
        index=False,
    )

    unmatched.to_csv(
        unmatched_file,
        index=False,
    )

    benchmark_duplicates.to_csv(
        benchmark_duplicates_file,
        index=False,
    )

    lgd_duplicates.to_csv(
        lgd_duplicates_file,
        index=False,
    )

    print("\n" + "=" * 70)
    print("OUTPUT FILES")
    print("=" * 70)

    print(exact_matches_file)
    print(unmatched_file)
    print(benchmark_duplicates_file)
    print(lgd_duplicates_file)


if __name__ == "__main__":
    main()