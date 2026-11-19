"""Pension finances: contributions, pensions, annual balance, and pension debt.

The mathematics is stated in ``docs/model.md``, section 2. All money amounts are
in units of the average wage of the base year.
"""

from dataclasses import dataclass
from typing import Literal

import numpy as np

from pension_simulator.data import N_AGES, CountryData, Indexation

BalancingRule = Literal["borrow", "raise_contributions", "cut_pensions"]

AGES = np.arange(N_AGES)


@dataclass(frozen=True)
class Finances:
    """Yearly finances of the pension system.

    Every array has one entry per simulated year, except ``pension_ratio``.

    Attributes
    ----------
    contributors : np.ndarray
        Number of contributors.
    retirees : np.ndarray
        Number of retirees.
    gdp : np.ndarray
        Gross domestic product.
    contributions : np.ndarray
        Contributions received, after the balancing rule.
    pensions : np.ndarray
        Pensions paid, after the balancing rule.
    gap : np.ndarray
        Contributions minus pensions before the balancing rule acts.
    debt : np.ndarray
        Pension debt at the start of the year.
    contribution_rate : np.ndarray
        Contribution rate in force.
    pension_ratio : np.ndarray
        Pension divided by the current average wage, by age, of shape ``[T + 1, 101]``.

    Examples
    --------
    .. code-block:: python

        finances = run_finances(country, population, retirement_age, 0.23, 0.5)
        debt_share = finances.debt / finances.gdp
    """

    contributors: np.ndarray
    retirees: np.ndarray
    gdp: np.ndarray
    contributions: np.ndarray
    pensions: np.ndarray
    gap: np.ndarray
    debt: np.ndarray
    contribution_rate: np.ndarray
    pension_ratio: np.ndarray


def effective_employment(data: CountryData) -> np.ndarray:
    """Return the employment rates that apply when people cannot yet retire.

    Recorded employment at ages above the current retirement age is low because
    most people there are retired. If the retirement age rises, these ages get
    the employment rate of the 55-to-59 age group.

    Parameters
    ----------
    data : CountryData
        The country.

    Returns
    -------
    np.ndarray
        Employment rates of shape ``[2, 101]``.

    Examples
    --------
    .. code-block:: python

        employment = effective_employment(country)
    """
    employment = data.employment.copy()
    late_career_rate = data.employment[:, 55:60].mean(axis=1, keepdims=True)
    employment[:, int(data.retirement_age) :] = late_career_rate
    return employment


def initial_pension_index(data: CountryData) -> np.ndarray:
    """Return the base-year pension of each age, per unit of benefit level.

    Under price indexation, a person who retired ``k`` years ago holds a pension
    set on the lower wage of that time. Under wage indexation, every pension
    follows the current wage.

    Parameters
    ----------
    data : CountryData
        The country.

    Returns
    -------
    np.ndarray
        Pension index of shape ``[101]``. It is 0 for ages that are not yet retired.

    Examples
    --------
    .. code-block:: python

        index = initial_pension_index(country)
    """
    index = np.zeros(N_AGES)
    retired = AGES >= int(data.retirement_age)
    years_retired = np.maximum(AGES - data.retirement_age, 0)
    if data.indexation == "prices":
        index[retired] = (1 + data.wage_growth) ** -years_retired[retired]
    else:
        index[retired] = 1.0
    return index


def fit_base_year(data: CountryData) -> tuple[float, float]:
    """Fit the contribution rate and the benefit level to recorded data.

    The fitted values make the base year reproduce recorded pension revenue and
    recorded pension spending as shares of GDP.

    Parameters
    ----------
    data : CountryData
        The country.

    Returns
    -------
    tuple[float, float]
        The contribution rate and the benefit level.

    Examples
    --------
    .. code-block:: python

        contribution_rate, benefit_level = fit_base_year(country)
    """
    working = np.clip(data.retirement_age - AGES, 0, 1)
    contributors = (data.population * effective_employment(data) * working).sum()
    gdp = contributors / data.labour_share

    # Contributions are rate x wage bill, and the wage bill is labour share x GDP.
    contribution_rate = data.pension_revenue_gdp / data.labour_share

    people = data.population.sum(axis=0)
    spending_per_unit = (people * (1 - working) * initial_pension_index(data)).sum()
    benefit_level = data.pension_spending_gdp * gdp / spending_per_unit
    return contribution_rate, benefit_level


def run_finances(
    data: CountryData,
    population: np.ndarray,
    retirement_age: np.ndarray,
    contribution_rate: float,
    benefit_level: float,
    balancing_rule: BalancingRule = "borrow",
    indexation: Indexation = "prices",
    wage_growth: float = 0.01,
    interest_rate: float = 0.01,
) -> Finances:
    """Compute the finances of the pension system for every simulated year.

    Parameters
    ----------
    data : CountryData
        The country.
    population : np.ndarray
        Projected population of shape ``[T + 1, 2, 101]``.
    retirement_age : np.ndarray
        Retirement age in each year, of shape ``[T + 1]``.
    contribution_rate : float
        Share of the average wage that each contributor pays.
    benefit_level : float
        A newly awarded pension divided by the average wage.
    balancing_rule : {"borrow", "raise_contributions", "cut_pensions"}
        Who pays for an annual deficit.
    indexation : {"prices", "wages"}
        How a pension rises after it is awarded.
    wage_growth : float
        Yearly growth of the average wage, above inflation.
    interest_rate : float
        Yearly interest rate on pension debt, above inflation.

    Returns
    -------
    Finances
        The yearly series.

    Examples
    --------
    .. code-block:: python

        rate, level = fit_base_year(country)
        ages = np.full(len(population), country.retirement_age)
        finances = run_finances(country, population, ages, rate, level)
    """
    n_years = len(population)
    employment = effective_employment(data)
    people = population.sum(axis=1)
    # Pension of each age per unit of benefit level. Cohorts carry it as they age.
    index = initial_pension_index(data)

    series: dict[str, np.ndarray] = {
        name: np.zeros(n_years) for name in Finances.__dataclass_fields__
    }
    series["pension_ratio"] = np.zeros((n_years, N_AGES))
    debt = 0.0

    for t in range(n_years):
        wage = (1 + wage_growth) ** t
        # The age group that contains the retirement age is split in proportion.
        working = np.clip(retirement_age[t] - AGES, 0, 1)
        retired = 1 - working
        # A cohort that retires this year gets a pension set on this year's wage.
        index[(retired > 0) & (index == 0)] = wage

        contributors = (population[t] * employment * working).sum()
        contributions = contribution_rate * wage * contributors
        pensions = benefit_level * (people[t] * retired * index).sum()
        gap = contributions - pensions

        # In a deficit year, the balancing rule decides who pays.
        rate, scale = contribution_rate, 1.0
        if gap < 0 and balancing_rule == "raise_contributions":
            rate = pensions / (wage * contributors)
            contributions = pensions
        elif gap < 0 and balancing_rule == "cut_pensions":
            scale = contributions / pensions
            pensions = contributions

        series["contributors"][t] = contributors
        series["retirees"][t] = (people[t] * retired).sum()
        series["gdp"][t] = wage * contributors / data.labour_share
        series["contributions"][t] = contributions
        series["pensions"][t] = pensions
        series["gap"][t] = gap
        series["debt"][t] = debt
        series["contribution_rate"][t] = rate
        series["pension_ratio"][t] = scale * benefit_level * retired * index / wage

        debt = debt * (1 + interest_rate) - (contributions - pensions)

        # Move to next year: pensions follow wages or stay level, and cohorts age.
        if indexation == "wages":
            index *= 1 + wage_growth
        index = np.roll(index, 1)
        index[0] = 0.0

    return Finances(**series)
