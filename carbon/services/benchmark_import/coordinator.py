from decimal import Decimal
from pathlib import Path

import pandas as pd
from django.db import transaction

from carbon.models import BenchmarkScope, CarbonBenchmark


class CarbonBenchmarkImportCoordinator:
    """
    Imports the validated India household carbon-footprint benchmark
    dataset into CarbonIQ.

    The coordinator is responsible for:
    - loading the validated benchmark CSV,
    - validating its structure,
    - importing district benchmarks,
    - importing the published India national benchmark,
    - maintaining idempotency,
    - and keeping the entire operation transactional.
    """

    BASE_DIR = Path(__file__).resolve().parents[3]

    BENCHMARK_FILE = (
        BASE_DIR
        / "data"
        / "benchmarks"
        / "processed"
        / "final_benchmark_dataset.csv"
    )

    SOURCE_NAME = (
        "Lee et al. (2021) — The scale and drivers "
        "of carbon footprints in households, cities "
        "and regions across India"
    )

    SOURCE_REFERENCE = (
        "https://doi.org/10.1016/"
        "j.gloenvcha.2020.102205"
    )

    REFERENCE_PERIOD = "2011-2012"
    UNIT = "tCO2/person/year"
    POPULATION_BASIS = "per_capita"

    # Published national average reported by the source paper.
    NATIONAL_BENCHMARK_VALUE = Decimal("0.56")

    REQUIRED_COLUMNS = {
        "original_district",
        "canonical_district",
        "state",
        "state_code",
        "district_code",
        "cf_per_capita",
        "overall_cf",
        "reference_period",
        "unit",
        "population_basis",
        "source",
        "source_reference",
    }

    @classmethod
    def import_all(cls) -> dict:
        """
        Import all benchmark records and return a structured summary.
        """

        cls._validate_source_file()

        dataframe = cls._load_dataframe()

        cls._validate_dataframe(dataframe)

        with transaction.atomic():
            district_result = cls._import_district_benchmarks(
                dataframe
            )

            national_created, national_already_current = (
                cls._import_national_benchmark()
            )

        return {
            "district_created": district_result["created"],
            "district_already_current": (
                district_result["already_current"]
            ),
            "national_created": national_created,
            "national_already_current": (
                national_already_current
            ),
            "total_created": (
                district_result["created"]
                + national_created
            ),
            "total_already_current": (
                district_result["already_current"]
                + national_already_current
            ),
            "total_records": len(dataframe) + 1,
        }

    # -----------------------------------------------------------------
    # Source loading
    # -----------------------------------------------------------------

    @classmethod
    def _validate_source_file(cls) -> None:
        """Ensure the validated benchmark CSV exists."""

        if not cls.BENCHMARK_FILE.exists():
            raise FileNotFoundError(
                "Validated benchmark dataset not found: "
                f"{cls.BENCHMARK_FILE}"
            )

    @classmethod
    def _load_dataframe(cls) -> pd.DataFrame:
        """Load the validated benchmark dataset."""

        try:
            return pd.read_csv(cls.BENCHMARK_FILE)
        except Exception as exc:
            raise ValueError(
                "Unable to read validated benchmark dataset: "
                f"{exc}"
            ) from exc

    # -----------------------------------------------------------------
    # Validation
    # -----------------------------------------------------------------

    @classmethod
    def _validate_dataframe(
        cls,
        dataframe: pd.DataFrame,
    ) -> None:
        """Validate the benchmark dataset before importing."""

        missing_columns = (
            cls.REQUIRED_COLUMNS
            - set(dataframe.columns)
        )

        if missing_columns:
            raise ValueError(
                "Benchmark dataset is missing required "
                f"columns: {sorted(missing_columns)}"
            )

        if dataframe.empty:
            raise ValueError(
                "Benchmark dataset is empty."
            )

        # Every benchmark row should have a valid district.
        if dataframe["canonical_district"].isna().any():
            raise ValueError(
                "Benchmark dataset contains missing "
                "canonical district names."
            )

        if dataframe["state"].isna().any():
            raise ValueError(
                "Benchmark dataset contains missing states."
            )

        if dataframe["district_code"].isna().any():
            raise ValueError(
                "Benchmark dataset contains missing "
                "district codes."
            )

        # Values must be numeric and non-negative.
        cf_values = pd.to_numeric(
            dataframe["cf_per_capita"],
            errors="coerce",
        )

        if cf_values.isna().any():
            raise ValueError(
                "Benchmark dataset contains invalid "
                "CF per capita values."
            )

        if (cf_values < 0).any():
            raise ValueError(
                "Benchmark dataset contains negative "
                "CF per capita values."
            )

        # Ensure the source metadata remains consistent.
        reference_periods = set(
            dataframe["reference_period"]
            .astype(str)
        )

        if reference_periods != {
            cls.REFERENCE_PERIOD
        }:
            raise ValueError(
                "Unexpected benchmark reference periods: "
                f"{sorted(reference_periods)}"
            )

        units = set(
            dataframe["unit"].astype(str)
        )

        if units != {cls.UNIT}:
            raise ValueError(
                "Unexpected benchmark units: "
                f"{sorted(units)}"
            )

        population_bases = set(
            dataframe["population_basis"].astype(str)
        )

        if population_bases != {
            cls.POPULATION_BASIS
        }:
            raise ValueError(
                "Unexpected population basis values: "
                f"{sorted(population_bases)}"
            )

    # -----------------------------------------------------------------
    # District import
    # -----------------------------------------------------------------

    @classmethod
    def _import_district_benchmarks(
        cls,
        dataframe: pd.DataFrame,
    ) -> dict:
        """Create or identify current district benchmarks."""

        created = 0
        already_current = 0

        for row in dataframe.itertuples(index=False):

            lookup = {
                "scope": BenchmarkScope.DISTRICT,
                "state": row.state,
                "district": row.canonical_district,
                "reference_period": row.reference_period,
                "source": row.source,
            }

            defaults = {
                "value": Decimal(
                    str(row.cf_per_capita)
                ),
                "unit": row.unit,
                "population_basis": (
                    row.population_basis
                ),
                "source_reference": (
                    row.source_reference
                ),
                "methodology": (
                    "Household consumption-based carbon "
                    "footprint estimated from Indian "
                    "Consumption Expenditure Survey data "
                    "and linked to the Eora global supply "
                    "chain database. Historical benchmark "
                    "reference period: 2011-2012."
                ),
                "effective_from": None,
                "effective_to": None,
                "is_active": True,
            }

            benchmark, was_created = (
                CarbonBenchmark.objects.get_or_create(
                    **lookup,
                    defaults=defaults,
                )
            )

            if was_created:
                created += 1
            else:
                # Existing records are intentionally not overwritten.
                already_current += 1

        return {
            "created": created,
            "already_current": already_current,
        }

    # -----------------------------------------------------------------
    # National benchmark
    # -----------------------------------------------------------------

    @classmethod
    def _import_national_benchmark(cls) -> tuple[int, int]:
        """Create the published India national benchmark."""

        lookup = {
            "scope": BenchmarkScope.NATIONAL,
            "state": None,
            "district": None,
            "reference_period": cls.REFERENCE_PERIOD,
            "source": cls.SOURCE_NAME,
        }

        defaults = {
            "value": cls.NATIONAL_BENCHMARK_VALUE,
            "unit": cls.UNIT,
            "population_basis": cls.POPULATION_BASIS,
            "source_reference": cls.SOURCE_REFERENCE,
            "methodology": (
                "Published national average household "
                "carbon footprint reported by Lee et al. "
                "(2021) for India, based on 2011-2012 "
                "consumption patterns."
            ),
            "effective_from": None,
            "effective_to": None,
            "is_active": True,
        }

        _, was_created = (
            CarbonBenchmark.objects.get_or_create(
                **lookup,
                defaults=defaults,
            )
        )

        if was_created:
            return 1, 0

        return 0, 1