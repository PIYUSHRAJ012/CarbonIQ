from pathlib import Path

import pandas as pd


PROJECT_ROOT = Path(__file__).resolve().parent.parent

CENSUS_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "2011-IndiaStateDistSbDistTwn-0000.xlsx"
)

BENCHMARK_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "raw"
    / "mmc2.csv"
)

UNMATCHED_FILE = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "processed"
    / "census_unmatched.csv"
)

OUTPUT_DIR = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "processed"
)


def normalize_name(value: object) -> str:
    """Normalize text for secondary name comparison."""

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


def main() -> None:
    # -----------------------------------------------------------------
    # Validate source files
    # -----------------------------------------------------------------

    for file_path in (
        CENSUS_FILE,
        BENCHMARK_FILE,
        UNMATCHED_FILE,
    ):
        if not file_path.exists():
            raise FileNotFoundError(
                f"Required file not found: {file_path}"
            )

    # -----------------------------------------------------------------
    # Load source data
    # -----------------------------------------------------------------

    print("=" * 70)
    print("LOADING SOURCE DATA")
    print("=" * 70)

    census = pd.read_excel(
        CENSUS_FILE,
        sheet_name="Data",
    )

    benchmark = pd.read_csv(
        BENCHMARK_FILE,
    )

    unmatched = pd.read_csv(
        UNMATCHED_FILE,
    )

    # -----------------------------------------------------------------
    # Extract ONLY the district TOTAL rows
    # -----------------------------------------------------------------

    district_rows = census[
        (census["Level"] == "DISTRICT")
        & (census["Subdistt"] == 0)
        & (census["Town/Village"] == 0)
        & (census["Ward"] == 0)
        & (census["EB"] == 0)
        & (census["TRU"] == "Total")
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

    # Remove the " Total" suffix from Census district names.
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

    district_rows["census_name_normalized"] = (
        district_rows["census_name"]
        .map(normalize_name)
    )

    # -----------------------------------------------------------------
    # Build state-code → state-name mapping
    # -----------------------------------------------------------------

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
    ].drop_duplicates(
        subset=["State"]
    )

    state_rows = state_rows.rename(
        columns={
            "State": "state_code",
            "Name": "state_name",
        }
    )

    district_rows = district_rows.merge(
        state_rows,
        on="state_code",
        how="left",
    )

    # -----------------------------------------------------------------
    # Prepare benchmark data
    # -----------------------------------------------------------------

    benchmark["cf_per_capita"] = pd.to_numeric(
        benchmark["CF per capita"],
        errors="coerce",
    )

    benchmark["overall_cf"] = pd.to_numeric(
        benchmark[" Overall CF "],
        errors="coerce",
    )

    benchmark["implied_population"] = (
        benchmark["overall_cf"]
        / benchmark["cf_per_capita"]
    )

    # Only unresolved benchmark records.
    unmatched_names = set(
        unmatched["District"].tolist()
    )

    benchmark_unmatched = benchmark[
        benchmark["District"].isin(unmatched_names)
    ].copy()

    # -----------------------------------------------------------------
    # Candidate generation
    # -----------------------------------------------------------------

    results = []

    for _, benchmark_row in benchmark_unmatched.iterrows():

        benchmark_name = benchmark_row["District"]
        normalized_benchmark = normalize_name(
            benchmark_name
        )

        implied_population = (
            benchmark_row["implied_population"]
        )

        if (
            pd.isna(implied_population)
            or implied_population <= 0
        ):
            continue

        # -------------------------------------------------------------
        # Calculate population-distance against every Census district.
        # -------------------------------------------------------------

        candidates = district_rows.copy()

        candidates["population_difference"] = (
            candidates["census_population"]
            - implied_population
        )

        candidates["population_difference_percent"] = (
            candidates["population_difference"]
            .abs()
            / implied_population
            * 100
        )

        # Secondary name similarity.
        candidates["name_exact"] = (
            candidates["census_name_normalized"]
            == normalized_benchmark
        )

        candidates["name_contains"] = (
            candidates["census_name_normalized"]
            .str.contains(
                normalized_benchmark,
                regex=False,
                na=False,
            )
            |
            candidates["census_name_normalized"].apply(
                lambda value: (
                    value in normalized_benchmark
                    or normalized_benchmark in value
                )
            )
        )

        # Population is the primary ranking signal.
        # Name evidence is retained for interpretation.
        candidates = candidates.sort_values(
            [
                "population_difference_percent",
                "name_exact",
                "name_contains",
            ],
            ascending=[
                True,
                False,
                False,
            ],
        )

        top_candidates = candidates.head(5)

        for rank, (_, candidate) in enumerate(
            top_candidates.iterrows(),
            start=1,
        ):
            results.append(
                {
                    "benchmark_district": benchmark_name,
                    "cf_per_capita": benchmark_row[
                        "cf_per_capita"
                    ],
                    "overall_cf": benchmark_row[
                        "overall_cf"
                    ],
                    "implied_population": round(
                        implied_population,
                        2,
                    ),
                    "rank": rank,
                    "candidate_state_code": int(
                        candidate["state_code"]
                    ),
                    "candidate_state": candidate[
                        "state_name"
                    ],
                    "candidate_district_code": int(
                        candidate["district_code"]
                    ),
                    "candidate_district": candidate[
                        "census_name"
                    ],
                    "census_population": int(
                        candidate["census_population"]
                    ),
                    "population_difference": round(
                        candidate[
                            "population_difference"
                        ],
                        2,
                    ),
                    "population_difference_percent": round(
                        candidate[
                            "population_difference_percent"
                        ],
                        2,
                    ),
                    "name_exact": bool(
                        candidate["name_exact"]
                    ),
                    "name_contains": bool(
                        candidate["name_contains"]
                    ),
                }
            )

    result_df = pd.DataFrame(results)

    # -----------------------------------------------------------------
    # Save complete candidate table
    # -----------------------------------------------------------------

    OUTPUT_DIR.mkdir(
        parents=True,
        exist_ok=True,
    )

    output_file = (
        OUTPUT_DIR
        / "population_match_candidates_clean.csv"
    )

    result_df.to_csv(
        output_file,
        index=False,
    )

    # -----------------------------------------------------------------
    # Console summary
    # -----------------------------------------------------------------

    print(
        f"Census district total rows: "
        f"{len(district_rows)}"
    )

    print(
        f"Unresolved benchmark records: "
        f"{len(benchmark_unmatched)}"
    )

    print()

    print("=" * 70)
    print("TOP POPULATION CANDIDATES")
    print("=" * 70)

    for benchmark_name in benchmark_unmatched[
        "District"
    ].tolist():

        print(f"\nBenchmark: {benchmark_name}")

        rows = result_df[
            result_df["benchmark_district"]
            == benchmark_name
        ].sort_values("rank")

        if rows.empty:
            print("  No candidates.")
            continue

        for _, row in rows.iterrows():

            flags = []

            if row["name_exact"]:
                flags.append("NAME-EXACT")

            elif row["name_contains"]:
                flags.append("NAME-SIMILAR")

            flag_text = (
                f" [{', '.join(flags)}]"
                if flags
                else ""
            )

            print(
                f"  {int(row['rank'])}. "
                f"{row['candidate_district']} "
                f"({row['candidate_state']}) "
                f"| population diff: "
                f"{row['population_difference_percent']:.2f}%"
                f"{flag_text}"
            )

    print("\n" + "=" * 70)
    print("OUTPUT")
    print("=" * 70)

    print(output_file)


if __name__ == "__main__":
    main()