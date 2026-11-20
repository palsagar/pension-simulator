"""The web layer: a thin, stateless FastAPI application on top of the model.

The same application serves the frontend, a folder of static files, at ``/``.
"""

import mimetypes
import os
from pathlib import Path

import numpy as np
from fastapi import FastAPI, HTTPException
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from pension_simulator.data import CountryData, load_country
from pension_simulator.finance import fit_base_year
from pension_simulator.population import FERTILITY_TARGET_YEAR
from pension_simulator.simulation import Scenario, simulate

DEFAULT_DATA_DIR = Path(__file__).parents[2] / "data" / "countries"
FRONTEND_DIR = Path(__file__).parents[2] / "frontend"

# The slim container image has no system table of file types, so the font type is named here.
mimetypes.add_type("font/woff2", ".woff2")


class Country(BaseModel):
    """One country with the default values of every control."""

    code: str
    name: str
    base_year: int
    end_year: int
    defaults: Scenario


class SimulationRequest(Scenario):
    """A scenario together with the country it applies to.

    ``include_population`` set to false leaves the population table out of the
    response. The table is most of the response, and it changes only with
    ``fertility``, ``net_migration``, and ``longevity_pace``. A client that
    already holds the table for these values does not need it again.
    """

    country: str
    include_population: bool = True


class CohortLedger(BaseModel):
    """Lifetime ledger of each birth cohort. Every list has one entry per cohort.

    Contributions and pensions are in years of average wage. A return is ``null``
    when it does not exist.
    """

    birth_years: list[int]
    lifetime_contributions: list[float]
    lifetime_pensions: list[float]
    return_above_wages: list[float | None]
    return_above_prices: list[float | None]


def optional(values: np.ndarray) -> list[float | None]:
    """Turn an array into a list, with ``None`` in place of missing values."""
    return [None if np.isnan(value) else float(value) for value in values]


class SimulationResponse(BaseModel):
    """Yearly results of one scenario. Every list has one entry per year.

    Money series are shares of GDP. ``population`` is indexed by year, then sex
    (0 is women, 1 is men), then age from 0 to 100. It is ``null`` when the
    request sets ``include_population`` to false.
    """

    years: list[int]
    retirement_age: list[float]
    contributors: list[float]
    retirees: list[float]
    support_ratio: list[float]
    contributions_gdp: list[float]
    pensions_gdp: list[float]
    annual_balance_gdp: list[float]
    pension_debt_gdp: list[float]
    contribution_rate: list[float]
    benefit_level: list[float]
    first_deficit_year: int | None
    population: list[list[list[int]]] | None
    cohorts: CohortLedger


def country_defaults(data: CountryData) -> Scenario:
    """Return the scenario that reproduces the baseline of a country.

    Parameters
    ----------
    data : CountryData
        The country.

    Returns
    -------
    Scenario
        A scenario with every control set to the country's default value.

    Examples
    --------
    .. code-block:: python

        defaults = country_defaults(france)
        print(defaults.contribution_rate)
    """
    contribution_rate, benefit_level = fit_base_year(data)
    return Scenario(
        retirement_age=data.retirement_age,
        contribution_rate=contribution_rate,
        benefit_level=benefit_level,
        indexation=data.indexation,
        wage_growth=data.wage_growth,
        interest_rate=data.interest_rate,
        fertility=float(data.fertility[FERTILITY_TARGET_YEAR - data.base_year].sum()),
        net_migration=float(data.migration.sum() / len(data.migration)),
    )


def create_app(data_dir: Path | None = None) -> FastAPI:
    """Create the application and load every country file once.

    Parameters
    ----------
    data_dir : Path, optional
        Folder with one ``.npz`` file per country. The default is the environment
        variable ``PENSION_DATA_DIR``, or ``data/countries`` in the repository.

    Returns
    -------
    FastAPI
        The application.

    Examples
    --------
    .. code-block:: python

        app = create_app(Path("data/countries"))
    """
    if data_dir is None:
        data_dir = Path(os.environ.get("PENSION_DATA_DIR", DEFAULT_DATA_DIR))
    countries = {data.code: data for data in map(load_country, sorted(data_dir.glob("*.npz")))}

    app = FastAPI(title="Pension Simulator")

    @app.get("/countries")
    def list_countries() -> list[Country]:
        return [
            Country(
                code=data.code,
                name=data.name,
                base_year=data.base_year,
                end_year=data.base_year + len(data.survival),
                defaults=country_defaults(data),
            )
            for data in countries.values()
        ]

    @app.post("/simulate")
    def run_simulation(request: SimulationRequest) -> SimulationResponse:
        if request.country not in countries:
            raise HTTPException(404, f"Unknown country: {request.country}")
        result = simulate(countries[request.country], request)
        finances = result.finances
        return SimulationResponse(
            years=result.years.tolist(),
            retirement_age=result.retirement_age.tolist(),
            contributors=finances.contributors.tolist(),
            retirees=finances.retirees.tolist(),
            support_ratio=(finances.contributors / finances.retirees).tolist(),
            contributions_gdp=(finances.contributions / finances.gdp).tolist(),
            pensions_gdp=(finances.pensions / finances.gdp).tolist(),
            annual_balance_gdp=(
                (finances.contributions - finances.pensions) / finances.gdp
            ).tolist(),
            pension_debt_gdp=(finances.debt / finances.gdp).tolist(),
            contribution_rate=finances.contribution_rate.tolist(),
            # Average pension over average wage: total pensions per retiree, in wage units.
            benefit_level=(
                finances.pensions
                * finances.contributors
                / (finances.retirees * finances.gdp * countries[request.country].labour_share)
            ).tolist(),
            first_deficit_year=result.first_deficit_year,
            # The table is about 100 kB of JSON, so a client can decline it.
            population=(
                result.population.round().astype(int).tolist()
                if request.include_population
                else None
            ),
            cohorts=CohortLedger(
                birth_years=result.ledger.birth_years.tolist(),
                lifetime_contributions=result.ledger.contributions.tolist(),
                lifetime_pensions=result.ledger.pensions.tolist(),
                return_above_wages=optional(result.ledger.return_above_wages),
                return_above_prices=optional(result.ledger.return_above_prices),
            ),
        )

    # Mounted last, so that the API routes above take precedence over the static files.
    app.mount("/", StaticFiles(directory=FRONTEND_DIR, html=True), name="frontend")
    return app
