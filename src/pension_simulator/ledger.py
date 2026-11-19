"""Lifetime ledger and internal rate of return of each birth cohort.

The mathematics is stated in ``docs/model.md``, section 3. The ledger follows a
representative person born in the country, from age 20 to age 100.
"""

from dataclasses import dataclass

import numpy as np
from scipy.optimize import brentq

from pension_simulator.data import N_AGES, CountryData
from pension_simulator.finance import AGES, Finances, effective_employment

FIRST_AGE = 20


@dataclass(frozen=True)
class Ledger:
    """Lifetime totals of each birth cohort. Every array has one entry per cohort.

    Attributes
    ----------
    birth_years : np.ndarray
        Year of birth of each cohort.
    contributions : np.ndarray
        Lifetime contributions, in years of average wage.
    pensions : np.ndarray
        Lifetime pensions, in years of average wage.
    return_above_wages : np.ndarray
        Internal rate of return above wage growth. ``nan`` if it does not exist.
    return_above_prices : np.ndarray
        Internal rate of return above price inflation. ``nan`` if it does not exist.

    Examples
    --------
    .. code-block:: python

        ledger = simulate(country, Scenario()).ledger
        born_1990 = ledger.birth_years == 1990
        print(ledger.pensions[born_1990] / ledger.contributions[born_1990])
    """

    birth_years: np.ndarray
    contributions: np.ndarray
    pensions: np.ndarray
    return_above_wages: np.ndarray
    return_above_prices: np.ndarray


def internal_rate_of_return(flows: np.ndarray) -> float:
    """Return the yearly rate at which a series of payments and receipts cancels out.

    Parameters
    ----------
    flows : np.ndarray
        Net receipts per year. Payments are negative.

    Returns
    -------
    float
        The rate, or ``nan`` if the flows never change sign.

    Examples
    --------
    .. code-block:: python

        rate = internal_rate_of_return(np.array([-1.0, 0.0, 1.21]))  # 0.10
    """
    periods = np.arange(len(flows))

    def present_value(rate: float) -> float:
        return float((flows / (1 + rate) ** periods).sum())

    low, high = -0.5, 1.0
    if present_value(low) * present_value(high) > 0:
        return float("nan")
    return float(brentq(present_value, low, high))


def lifetime_ledger(
    data: CountryData,
    finances: Finances,
    retirement_age: np.ndarray,
    survival: np.ndarray,
    wage_growth: float,
) -> Ledger:
    """Compute the lifetime ledger of every cohort that the data covers in full.

    Years before the base year use recorded data. Later years use the simulation.

    Parameters
    ----------
    data : CountryData
        The country.
    finances : Finances
        Simulated finances from the base year onward.
    retirement_age : np.ndarray
        Simulated retirement age in each year, of shape ``[T + 1]``.
    survival : np.ndarray
        Survival probabilities used in the simulation, of shape ``[T, 2, 101]``.
    wage_growth : float
        Yearly growth of the average wage from the base year, above inflation.

    Returns
    -------
    Ledger
        One entry per cohort, from the first cohort aged 20 at the start of the
        recorded history to the last cohort aged 100 at the end of the simulation.

    Examples
    --------
    .. code-block:: python

        ledger = lifetime_ledger(country, finances, retirement_age, survival, 0.01)
    """
    n_history = len(data.history_wage)
    n_simulated = len(retirement_age)
    first_year = data.base_year - n_history
    last_year = data.base_year + n_simulated - 1

    # Join recorded history and simulation into series that run over all years.
    contribution_rate = np.concatenate([data.history_contribution_rate, finances.contribution_rate])
    wage = np.concatenate([data.history_wage, (1 + wage_growth) ** np.arange(n_simulated)])
    # The representative person is the average of a woman and a man.
    yearly_survival = np.concatenate([data.history_survival, survival]).mean(axis=1)
    all_retirement_ages = np.concatenate([np.full(n_history, data.retirement_age), retirement_age])
    working = np.clip(all_retirement_ages[:, None] - AGES, 0, 1)
    # Pensions paid before the base year take the base-year level by age.
    pension_ratio = np.concatenate(
        [np.broadcast_to(finances.pension_ratio[0], (n_history, N_AGES)), finances.pension_ratio]
    )
    employment = effective_employment(data).mean(axis=0)

    ages = np.arange(FIRST_AGE, N_AGES)
    birth_years = np.arange(first_year - FIRST_AGE, last_year - ages[-1] + 1)
    columns: list[tuple[float, float, float, float]] = []
    for birth_year in birth_years:
        # A cohort moves along the diagonal: one year older in each calendar year.
        years = birth_year + ages - first_year
        alive = np.concatenate([[1.0], yearly_survival[years[:-1], ages[:-1]].cumprod()])

        paid = alive * employment[ages] * working[years, ages] * contribution_rate[years]
        received = alive * pension_ratio[years, ages]
        net = received - paid
        columns.append(
            (
                paid.sum(),
                received.sum(),
                # In years of average wage, growth of the economy drops out.
                internal_rate_of_return(net),
                # In constant euros, each year counts at the wage of that year.
                internal_rate_of_return(net * wage[years]),
            )
        )

    contributions, pensions, above_wages, above_prices = np.array(columns).T
    return Ledger(birth_years, contributions, pensions, above_wages, above_prices)
