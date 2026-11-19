"""Run one scenario for one country: population first, then finances."""

from dataclasses import dataclass

import numpy as np
from pydantic import BaseModel, Field

from pension_simulator.data import CountryData, Indexation
from pension_simulator.finance import (
    BalancingRule,
    Finances,
    fit_base_year,
    run_finances,
)
from pension_simulator.ledger import Ledger, lifetime_ledger
from pension_simulator.population import (
    adjust_fertility,
    adjust_migration,
    adjust_survival,
    project,
)


class Scenario(BaseModel):
    """The choices of the user. A value of ``None`` means the country's default.

    Attributes
    ----------
    retirement_age : float or None
        Target retirement age.
    retirement_age_year : int
        Year in which the target retirement age is reached.
    contribution_rate : float or None
        Share of the average wage that each contributor pays.
    benefit_level : float or None
        A newly awarded pension divided by the average wage.
    balancing_rule : {"borrow", "raise_contributions", "cut_pensions"}
        Who pays for an annual deficit.
    indexation : {"prices", "wages"} or None
        How a pension rises after it is awarded.
    wage_growth : float or None
        Yearly growth of the average wage, above inflation.
    interest_rate : float or None
        Yearly interest rate on pension debt, above inflation.
    fertility : float or None
        Children per woman in 2040.
    net_migration : float or None
        Net migrants per year, averaged over the simulation.
    longevity_pace : float
        Share of the projected fall in mortality that takes place.

    Examples
    --------
    .. code-block:: python

        scenario = Scenario(retirement_age=67, retirement_age_year=2035)
    """

    retirement_age: float | None = Field(None, ge=55, le=75)
    retirement_age_year: int = Field(2035, ge=2025, le=2100)
    contribution_rate: float | None = Field(None, ge=0, le=0.6)
    benefit_level: float | None = Field(None, ge=0, le=1.5)
    balancing_rule: BalancingRule = "borrow"
    indexation: Indexation | None = None
    wage_growth: float | None = Field(None, ge=-0.01, le=0.04)
    interest_rate: float | None = Field(None, ge=-0.02, le=0.06)
    fertility: float | None = Field(None, ge=0.5, le=4)
    net_migration: float | None = Field(None, ge=-1_000_000, le=2_000_000)
    longevity_pace: float = Field(1.0, ge=0, le=1.5)


@dataclass(frozen=True)
class Simulation:
    """The result of one scenario.

    Attributes
    ----------
    years : np.ndarray
        Calendar years, of shape ``[T + 1]``.
    population : np.ndarray
        People by year, sex, and age, of shape ``[T + 1, 2, 101]``.
    retirement_age : np.ndarray
        Retirement age in each year.
    finances : Finances
        Yearly finances of the pension system.
    ledger : Ledger
        Lifetime ledger of each birth cohort.

    Examples
    --------
    .. code-block:: python

        result = simulate(country, Scenario(retirement_age=67))
        print(result.first_deficit_year)
    """

    years: np.ndarray
    population: np.ndarray
    retirement_age: np.ndarray
    finances: Finances
    ledger: Ledger

    @property
    def first_deficit_year(self) -> int | None:
        """First year in which contributions fall short of pensions, if any."""
        deficit_years = self.years[self.finances.gap < 0]
        return int(deficit_years[0]) if len(deficit_years) else None


def simulate(data: CountryData, scenario: Scenario) -> Simulation:
    """Run one scenario for one country.

    Parameters
    ----------
    data : CountryData
        The country.
    scenario : Scenario
        The choices of the user.

    Returns
    -------
    Simulation
        Population and finances for every year from the base year to the end.

    Examples
    --------
    .. code-block:: python

        france = load_country(Path("data/countries/FRA.npz"))
        result = simulate(france, Scenario(retirement_age=65))
    """
    # Apply the demographic choices of the user to the baseline rates.
    survival = adjust_survival(data.survival, scenario.longevity_pace)
    survival_birth = adjust_survival(data.survival_birth, scenario.longevity_pace)
    fertility = data.fertility
    if scenario.fertility is not None:
        fertility = adjust_fertility(fertility, data.base_year, scenario.fertility)
    migration = data.migration
    if scenario.net_migration is not None:
        migration = adjust_migration(migration, scenario.net_migration)

    population = project(data.population, survival, survival_birth, fertility, migration)
    years = data.base_year + np.arange(len(population))

    # The retirement age moves in a straight line to its target, then stays there.
    target_age = data.retirement_age if scenario.retirement_age is None else scenario.retirement_age
    phase_in_years = max(scenario.retirement_age_year - data.base_year, 1)
    progress = np.clip((years - data.base_year) / phase_in_years, 0, 1)
    if scenario.retirement_age_year <= data.base_year:
        progress = np.ones(len(years))
    retirement_age = data.retirement_age + progress * (target_age - data.retirement_age)

    fitted_rate, fitted_level = fit_base_year(data)

    def choice[T](value: T | None, default: T) -> T:
        return default if value is None else value

    wage_growth = choice(scenario.wage_growth, data.wage_growth)
    finances = run_finances(
        data,
        population,
        retirement_age,
        contribution_rate=choice(scenario.contribution_rate, fitted_rate),
        benefit_level=choice(scenario.benefit_level, fitted_level),
        balancing_rule=scenario.balancing_rule,
        indexation=choice(scenario.indexation, data.indexation),
        wage_growth=wage_growth,
        interest_rate=choice(scenario.interest_rate, data.interest_rate),
    )
    ledger = lifetime_ledger(data, finances, retirement_age, survival, wage_growth)
    return Simulation(years, population, retirement_age, finances, ledger)
