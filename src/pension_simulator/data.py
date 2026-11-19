"""Country data: the fixed inputs of the model for one country.

Array conventions used across the package:

- Sex index 0 is women, 1 is men.
- Age index runs from 0 to 100. The last group holds everyone aged 100 or more.
- Year index 0 is the base year. Rates with ``T`` years describe the steps from
  each year to the next, so a projection covers ``T + 1`` years.
"""

import json
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Literal

import numpy as np

Indexation = Literal["prices", "wages"]

N_AGES = 101
ARRAY_FIELDS = (
    "population",
    "survival",
    "survival_birth",
    "fertility",
    "migration",
    "employment",
)


@dataclass(frozen=True)
class CountryData:
    """Fixed model inputs for one country.

    Attributes
    ----------
    code : str
        Three-letter country code, for example ``"FRA"``.
    name : str
        Country name in English.
    base_year : int
        First year of the simulation.
    population : np.ndarray
        People at the start of the base year, of shape ``[2, 101]``.
    survival : np.ndarray
        Probability of surviving one year, of shape ``[T, 2, 101]``.
    survival_birth : np.ndarray
        Probability that a newborn survives the calendar year, of shape ``[T, 2]``.
    fertility : np.ndarray
        Births per woman per year by age of mother, of shape ``[T, 101]``.
    migration : np.ndarray
        Net migrants by age at the end of the year, of shape ``[T, 2, 101]``.
    employment : np.ndarray
        Share of people in employment, of shape ``[2, 101]``.
    retirement_age : float
        Current retirement age.
    labour_share : float
        Wage bill divided by GDP.
    pension_spending_gdp : float
        Recorded pension spending as a share of GDP.
    pension_revenue_gdp : float
        Recorded pension-system revenue from all sources as a share of GDP.
    indexation : {"prices", "wages"}
        The country's own pension indexation rule: ``"prices"`` or ``"wages"``.
    wage_growth : float
        Default yearly growth of the average wage, above inflation.
    interest_rate : float
        Default yearly interest rate on pension debt, above inflation.

    Examples
    --------
    .. code-block:: python

        france = load_country(Path("data/countries/FRA.npz"))
        print(france.name, france.retirement_age)
    """

    code: str
    name: str
    base_year: int
    population: np.ndarray
    survival: np.ndarray
    survival_birth: np.ndarray
    fertility: np.ndarray
    migration: np.ndarray
    employment: np.ndarray
    retirement_age: float
    labour_share: float
    pension_spending_gdp: float
    pension_revenue_gdp: float
    indexation: Indexation
    wage_growth: float
    interest_rate: float


def save_country(data: CountryData, path: Path) -> None:
    """Write one country to a compressed NumPy file.

    Parameters
    ----------
    data : CountryData
        The country to write.
    path : Path
        Target file, with the suffix ``.npz``.

    Examples
    --------
    .. code-block:: python

        save_country(france, Path("data/countries/FRA.npz"))
    """
    fields = asdict(data)
    arrays = {name: fields.pop(name) for name in ARRAY_FIELDS}
    # The remaining fields are plain numbers and strings, stored as one JSON text.
    np.savez_compressed(path, meta=json.dumps(fields), **arrays)


def load_country(path: Path) -> CountryData:
    """Read one country from a file written by :func:`save_country`.

    Parameters
    ----------
    path : Path
        File to read.

    Returns
    -------
    CountryData
        The country stored in the file.

    Examples
    --------
    .. code-block:: python

        france = load_country(Path("data/countries/FRA.npz"))
    """
    with np.load(path) as file:
        meta = json.loads(str(file["meta"]))
        arrays = {name: file[name] for name in ARRAY_FIELDS}
    return CountryData(**meta, **arrays)
