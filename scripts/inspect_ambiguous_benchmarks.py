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


AMBIGUOUS_DISTRICTS = {
    "Hamirpur",
    "Bilaspur",
    "Aurangabad",
    "Raigarh",
}


def normalize_name(value: object) -> str:
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
    print("=" * 70)
    print("AMBIGUOUS HISTORICAL BENCHMARK INSPECTION")
    print("=" * 70)

    benchmark = pd.read_csv(BENCHMARK_FILE)

    census = pd.read_excel(
        CENSUS_FILE,
        sheet_name="Data",
    )

    # ---------------------------------------------------------------
    # Extract historical Census district-total records
    # ---------------------------------------------------------------

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

    district_rows["normalized"] = (
        district_rows["census_name"]
        .map(normalize_name)
    )

    # ---------------------------------------------------------------
    # Extract state names
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

    # ---------------------------------------------------------------
    # Inspect each ambiguous benchmark
    # ---------------------------------------------------------------

    for benchmark_name in sorted(AMBIGUOUS_DISTRICTS):

        rows = benchmark[
            benchmark["District"].astype(str).str.strip()
            == benchmark_name
        ]

        if rows.empty:
            print(
                f"\nWARNING: benchmark district not found: "
                f"{benchmark_name}"
            )
            continue

        print("\n" + "=" * 70)
        print(f"BENCHMARK: {benchmark_name}")
        print("=" * 70)

        for index, benchmark_row in rows.iterrows():

            cf_per_capita = float(
                benchmark_row["CF per capita"]
            )

            overall_cf = float(
                benchmark_row[" Overall CF "]
            )

            implied_population = (
                overall_cf / cf_per_capita
            )

            print(
                f"\nBenchmark record #{index}"
            )

            print(
                f"CF per capita: "
                f"{cf_per_capita}"
            )

            print(
                f"Overall CF: "
                f"{overall_cf}"
            )

            print(
                f"Implied population: "
                f"{implied_population:.2f}"
            )

            normalized_benchmark = normalize_name(
                benchmark_name
            )

            candidates = district_rows[
                district_rows["normalized"]
                .str.contains(
                    normalized_benchmark,
                    regex=False,
                    na=False,
                )
                |
                district_rows["normalized"].apply(
                    lambda value: (
                        value in normalized_benchmark
                        or normalized_benchmark in value
                    )
                )
            ].copy()

            if candidates.empty:
                print("No textual Census candidates found.")
                continue

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

            candidates = candidates.sort_values(
                "population_difference_percent"
            )

            print("\nCandidates:")

            for _, candidate in candidates.iterrows():

                print(
                    f"  {candidate['census_name']} "
                    f"| {candidate['state_name']} "
                    f"| State Code: "
                    f"{int(candidate['state_code'])} "
                    f"| District Code: "
                    f"{int(candidate['district_code'])} "
                    f"| Census Population: "
                    f"{int(candidate['census_population'])} "
                    f"| Difference: "
                    f"{candidate['population_difference_percent']:.4f}%"
                )


if __name__ == "__main__":
    main()