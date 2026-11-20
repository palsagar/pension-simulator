"""Build one data file per country from public United Nations, OECD, and AMECO data.

Run it from the repository root:

.. code-block:: bash

    uv run python scripts/build_country_data.py

The script downloads the source files to ``data/raw`` (not committed) on the first
run, and writes ``data/countries/<code>.npz`` (committed). The running service
reads only the files in ``data/countries``.
"""

import csv
import gzip
import io
import urllib.request
import zipfile
from collections.abc import Iterator
from pathlib import Path

import numpy as np

from pension_simulator.data import N_AGES, CountryData, Indexation, save_country
from pension_simulator.population import SHARE_OF_BIRTHS

ROOT = Path(__file__).parents[1]
RAW_DIR = ROOT / "data" / "raw"
OUT_DIR = ROOT / "data" / "countries"

BASE_YEAR = 2025
END_YEAR = 2100
N_YEARS = END_YEAR - BASE_YEAR
# Recorded pension spending starts in 1980 for all four countries.
HISTORY_START = 1980
N_HISTORY = BASE_YEAR - HISTORY_START

UN_URL = "https://population.un.org/wpp/assets/Excel%20Files/1_Indicator%20(Standard)/CSV_FILES/"
UN_POPULATION = "WPP2024_Population1JanuaryBySingleAgeSex_Medium_2024-2100"
UN_LIFE_TABLE = "WPP2024_Life_Table_Complete_Medium_{sex}_{period}"
UN_FERTILITY = "WPP2024_Fertility_by_Age1"
UN_INDICATORS = "WPP2024_Demographic_Indicators_Medium"

OECD_URL = "https://sdmx.oecd.org/public/rest/data/"
OECD_EMPLOYMENT = (
    "OECD.ELS.SAE,DSD_LFS@DF_LFS_INDIC,/FRA+DEU+ITA+ESP.EMP_RATIO..M+F..?startPeriod=2023"
)
OECD_PENSION_SPENDING = "OECD.ELS.SPD,DSD_SOCX_AGG@DF_PUB_OLD,1.0/FRA+DEU+ITA+ESP.......?"
AMECO_URL = "https://ec.europa.eu/economy_finance/db_indicators/ameco/documents/ameco7.zip"

# Values that no dataset supplies in a usable form. The retirement age is the
# standard age written in law for a person who retires in the base year.
COUNTRIES: dict[str, tuple[str, float, Indexation]] = {
    "FRA": ("France", 62.75, "prices"),
    "DEU": ("Germany", 66.17, "wages"),
    "ITA": ("Italy", 67.0, "prices"),
    "ESP": ("Spain", 66.67, "prices"),
}
WAGE_GROWTH = 0.01
INTEREST_RATE = 0.02


def fetch(url: str, path: Path) -> None:
    """Download a file, unless it is already present."""
    if not path.exists():
        print(f"Downloading {path.name}")
        with urllib.request.urlopen(url) as response:
            path.write_bytes(response.read())


def fetch_un(name: str) -> Path:
    """Download one United Nations file and keep only the rows of our countries.

    The source files hold every country in the world and are up to 300 MB each,
    so the rows are filtered while the download streams.
    """
    path = RAW_DIR / f"{name}.csv"
    if not path.exists():
        print(f"Downloading {name}")
        with urllib.request.urlopen(f"{UN_URL}{name}.csv.gz") as response:
            lines = io.TextIOWrapper(gzip.GzipFile(fileobj=response), encoding="utf-8-sig")
            with path.open("w") as out:
                out.write(next(lines))
                out.writelines(line for line in lines if line.split(",", 4)[3] in COUNTRIES)
    return path


def read_csv(
    path: Path, encoding: str = "utf-8-sig", delimiter: str = ","
) -> Iterator[dict[str, str]]:
    """Yield the rows of a CSV file as dictionaries."""
    with path.open(encoding=encoding, newline="") as file:
        yield from csv.DictReader(file, delimiter=delimiter)


def un_population() -> dict[str, np.ndarray]:
    """Read population on 1 January by country, as arrays ``[year, sex, age]``."""
    result = {code: np.zeros((N_YEARS + 1, 2, N_AGES)) for code in COUNTRIES}
    for row in read_csv(fetch_un(UN_POPULATION)):
        year = int(row["Time"]) - BASE_YEAR
        if 0 <= year <= N_YEARS:
            age = int(row["AgeGrpStart"])
            # The source counts people in thousands.
            result[row["ISO3_code"]][year, 0, age] = float(row["PopFemale"]) * 1000
            result[row["ISO3_code"]][year, 1, age] = float(row["PopMale"]) * 1000
    return result


def un_survival(
    first_year: int, n_years: int
) -> tuple[dict[str, np.ndarray], dict[str, np.ndarray]]:
    """Read survival probabilities by country from the life tables.

    Returns the yearly survival ``[year, sex, age]`` and the survival of newborns
    to the end of their calendar year of birth ``[year, sex]``, for ``n_years``
    years from ``first_year``.
    """
    person_years = {code: np.zeros((n_years, 2, N_AGES)) for code in COUNTRIES}
    for sex, name in enumerate(("Female", "Male")):
        for period in ("1950-2023", "2024-2100"):
            for row in read_csv(fetch_un(UN_LIFE_TABLE.format(sex=name, period=period))):
                year = int(row["Time"]) - first_year
                if 0 <= year < n_years:
                    age = int(row["AgeGrpStart"])
                    person_years[row["ISO3_code"]][year, sex, age] = float(row["Lx"])

    survival, survival_birth = {}, {}
    for code, lived in person_years.items():
        ratio = np.empty_like(lived)
        # People aged x at the start of the year are aged x + 1 at its end.
        ratio[:, :, :-2] = lived[:, :, 1:-1] / lived[:, :, :-2]
        # The two oldest groups both survive into the open group aged 100 or more.
        ratio[:, :, -2:] = (lived[:, :, -1] / (lived[:, :, -2] + lived[:, :, -1]))[:, :, None]
        survival[code] = ratio
        # A life table starts with 100,000 births.
        survival_birth[code] = lived[:, :, 0] / 100_000
    return survival, survival_birth


def un_fertility() -> dict[str, np.ndarray]:
    """Read births per woman per year by country, as arrays ``[year, age]``."""
    result = {code: np.zeros((N_YEARS, N_AGES)) for code in COUNTRIES}
    for row in read_csv(fetch_un(UN_FERTILITY)):
        year = int(row["Time"]) - BASE_YEAR
        if 0 <= year < N_YEARS and row["Variant"] == "Medium":
            # The source counts births per 1,000 women.
            result[row["ISO3_code"]][year, int(row["AgeGrpStart"])] = float(row["ASFR"]) / 1000
    return result


def un_net_migration() -> dict[str, np.ndarray]:
    """Read the published total of net migrants per year by country."""
    result = {code: np.zeros(N_YEARS) for code in COUNTRIES}
    for row in read_csv(fetch_un(UN_INDICATORS)):
        year = int(row["Time"]) - BASE_YEAR
        if 0 <= year < N_YEARS:
            result[row["ISO3_code"]][year] = float(row["NetMigrations"]) * 1000
    return result


def residual_migration(
    population: np.ndarray,
    survival: np.ndarray,
    survival_birth: np.ndarray,
    fertility: np.ndarray,
) -> np.ndarray:
    """Derive net migrants by age and sex as the change that survival and births do not explain.

    The United Nations publishes net migration as a yearly total only. This
    residual makes the model reproduce the United Nations projection exactly.
    """
    now, nxt = population[:-1], population[1:]
    survivors = now * survival
    expected = np.empty_like(now)
    expected[:, :, 1:] = survivors[:, :, :-1]
    expected[:, :, -1] += survivors[:, :, -1]
    women = (now[:, 0, 1:] + nxt[:, 0, 1:]) / 2
    births = (fertility[:, 1:] * women).sum(axis=1)
    expected[:, :, 0] = births[:, None] * SHARE_OF_BIRTHS * survival_birth
    return nxt - expected


def oecd_rows(query: str, name: str) -> Iterator[dict[str, str]]:
    path = RAW_DIR / name
    fetch(f"{OECD_URL}{query}&format=csvfilewithlabels", path)
    return read_csv(path)


def employment_rates() -> dict[str, np.ndarray]:
    """Read employment rates by country, spread from five-year groups to single ages."""
    latest: dict[tuple[str, int, int], tuple[str, float]] = {}
    for row in oecd_rows(OECD_EMPLOYMENT, "oecd_employment.csv"):
        # Keep five-year groups only, for example "Y55T59".
        low, _, high = row["AGE"][1:].partition("T")
        if not (low.isdigit() and high.isdigit() and int(high) - int(low) == 4):
            continue
        key = (row["REF_AREA"], "FM".index(row["SEX"]), int(low))
        if key not in latest or row["TIME_PERIOD"] > latest[key][0]:
            latest[key] = (row["TIME_PERIOD"], float(row["OBS_VALUE"]) / 100)

    result = {code: np.zeros((2, N_AGES)) for code in COUNTRIES}
    for (code, sex, low), (_, rate) in latest.items():
        result[code][sex, low : low + 5] = rate
    return result


def pension_spending() -> dict[str, dict[int, float]]:
    """Read recorded public pension spending as a share of GDP, by country and year."""
    result: dict[str, dict[int, float]] = {code: {} for code in COUNTRIES}
    for row in oecd_rows(OECD_PENSION_SPENDING, "oecd_socx_old_history.csv"):
        if row["UNIT_MEASURE"] == "PT_B1GQ":
            result[row["REF_AREA"]][int(row["TIME_PERIOD"])] = float(row["OBS_VALUE"]) / 100
    return result


def ameco_series(series: str) -> dict[str, dict[int, float]]:
    """Read one yearly AMECO series by country.

    Germany starts in 1991. Earlier years take the values of West Germany.
    """
    path = RAW_DIR / "ameco7.zip"
    fetch(AMECO_URL, path)
    with zipfile.ZipFile(path) as archive:
        archive.extract("AMECO7.TXT", RAW_DIR)
    result: dict[str, dict[int, float]] = {code: {} for code in COUNTRIES}
    west_germany: dict[int, float] = {}
    for row in read_csv(RAW_DIR / "AMECO7.TXT", encoding="latin-1", delimiter=";"):
        code, *_, name = row["CODE"].split(".")
        if name != series or code not in (*COUNTRIES, "D_W"):
            continue
        values = {
            year: float(row[str(year)])
            for year in range(1960, BASE_YEAR + 1)
            if row[str(year)].strip() not in ("", "NA")
        }
        if code == "D_W":
            west_germany = values
        else:
            result[code] = values
    result["DEU"] = west_germany | result["DEU"]
    return result


def main() -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    OUT_DIR.mkdir(parents=True, exist_ok=True)

    population = un_population()
    survival, survival_birth = un_survival(BASE_YEAR, N_YEARS)
    history_survival, _ = un_survival(HISTORY_START, N_HISTORY)
    fertility = un_fertility()
    published_migration = un_net_migration()
    employment = employment_rates()
    spending = pension_spending()
    # ALCD0 is the adjusted wage share as a percentage of GDP at market prices.
    labour_share = ameco_series("ALCD0")
    # RWCDC is real compensation per employee, deflated by consumer prices.
    real_wage = ameco_series("RWCDC")
    history_years = range(HISTORY_START, BASE_YEAR)

    for code, (name, retirement_age, indexation) in COUNTRIES.items():
        migration = residual_migration(
            population[code], survival[code], survival_birth[code], fertility[code]
        )
        # Check the derived migrants against the total that the United Nations publishes.
        derived = migration.sum(axis=(1, 2))
        worst = np.abs(derived - published_migration[code]).max()
        print(
            f"{code}: net migration per year, derived {derived.mean():,.0f}, "
            f"published {published_migration[code].mean():,.0f}, largest yearly gap {worst:,.0f}"
        )

        if abs(derived.mean() - published_migration[code].mean()) > 0.02 * abs(
            published_migration[code].mean()
        ):
            raise ValueError(f"{code}: derived net migration differs from the published total")

        # The latest recorded year stands in for the years after it.
        last_recorded = max(spending[code])
        latest_spending = spending[code][last_recorded]
        latest_labour_share = labour_share[code][BASE_YEAR - 1] / 100
        # Past contribution rates assume that revenue matched spending in each year.
        history_contribution_rate = np.array(
            [
                spending[code][min(year, last_recorded)] / (labour_share[code][year] / 100)
                for year in history_years
            ]
        )
        history_wage = np.array(
            [real_wage[code][year] / real_wage[code][BASE_YEAR] for year in history_years]
        )

        save_country(
            CountryData(
                code=code,
                name=name,
                base_year=BASE_YEAR,
                population=population[code][0],
                survival=survival[code],
                survival_birth=survival_birth[code],
                fertility=fertility[code],
                migration=migration,
                employment=employment[code],
                retirement_age=retirement_age,
                labour_share=latest_labour_share,
                pension_spending_gdp=latest_spending,
                # The base year starts balanced. See docs/adr/0002.
                pension_revenue_gdp=latest_spending,
                indexation=indexation,
                wage_growth=WAGE_GROWTH,
                interest_rate=INTEREST_RATE,
                history_contribution_rate=history_contribution_rate,
                history_wage=history_wage,
                history_survival=history_survival[code],
            ),
            OUT_DIR / f"{code}.npz",
        )


if __name__ == "__main__":
    main()
