from difflib import SequenceMatcher
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

PROCESSED_DIR = (
    PROJECT_ROOT
    / "data"
    / "benchmarks"
    / "processed"
)

UNMATCHED_FILE = (
    PROCESSED_DIR
    / "census_unmatched.csv"
)


def normalize_name(value: object) -> str:
    """Conservative normalization used for candidate generation."""
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


def similarity(left: str, right: str) -> float:
    """Return similarity percentage using standard-library matching."""
    return SequenceMatcher(
        None,
        left,
        right,
    ).ratio() * 100


def main() -> None:
    if not CENSUS_FILE.exists():
        raise FileNotFoundError(
            f"Census file not found: {CENSUS_FILE}"
        )

    if not UNMATCHED_FILE.exists():
        raise FileNotFoundError(
            f"Unmatched file not found: {UNMATCHED_FILE}"
        )

    census = pd.read_excel(
        CENSUS_FILE,
        sheet_name="Sheet1",
    )

    unmatched = pd.read_csv(UNMATCHED_FILE)

    # ---------------------------------------------------------------
    # Extract historical district records
    # ---------------------------------------------------------------

    census_districts = (
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
                "Town-Village Name": "census_district_name"
            }
        )
    )

    # State-level records
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

    census_districts = census_districts.merge(
        states,
        on="State Code",
        how="left",
    )

    census_districts["normalized"] = (
        census_districts["census_district_name"]
        .map(normalize_name)
    )

    # ---------------------------------------------------------------
    # Generate candidate matches
    # ---------------------------------------------------------------

    results = []

    for benchmark_name in unmatched["District"].tolist():

        normalized_benchmark = normalize_name(
            benchmark_name
        )

        candidates = []

        for _, census_row in census_districts.iterrows():

            score = similarity(
                normalized_benchmark,
                census_row["normalized"],
            )

            candidates.append(
                (
                    score,
                    census_row["state_name"],
                    census_row["census_district_name"],
                    census_row["State Code"],
                    census_row["District Code"],
                )
            )

        candidates.sort(
            key=lambda item: item[0],
            reverse=True,
        )

        for rank, candidate in enumerate(
            candidates[:5],
            start=1,
        ):
            (
                score,
                state_name,
                district_name,
                state_code,
                district_code,
            ) = candidate

            results.append(
                {
                    "benchmark_district": benchmark_name,
                    "rank": rank,
                    "similarity": round(score, 2),
                    "candidate_state": state_name,
                    "candidate_district": district_name,
                    "state_code": state_code,
                    "district_code": district_code,
                }
            )

    candidates_df = pd.DataFrame(results)

    output_file = (
        PROCESSED_DIR
        / "historical_match_candidates.csv"
    )

    candidates_df.to_csv(
        output_file,
        index=False,
    )

    # ---------------------------------------------------------------
    # Print results for review
    # ---------------------------------------------------------------

    print("=" * 70)
    print("HISTORICAL MATCH CANDIDATES")
    print("=" * 70)

    for district in unmatched["District"].tolist():

        print(f"\nBenchmark: {district}")

        district_candidates = candidates_df[
            candidates_df["benchmark_district"] == district
        ].sort_values("rank")

        for _, row in district_candidates.iterrows():
            print(
                f"  {int(row['rank'])}. "
                f"{row['candidate_district']} "
                f"({row['candidate_state']}) "
                f"→ {row['similarity']:.2f}%"
            )

    print("\n" + "=" * 70)
    print("OUTPUT")
    print("=" * 70)
    print(output_file)


if __name__ == "__main__":
    main()