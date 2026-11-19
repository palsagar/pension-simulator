"""A small invented country, so that tests do not depend on downloaded data."""

import numpy as np
import pytest

from pension_simulator.data import N_AGES, CountryData

N_YEARS = 75
N_HISTORY = 45


@pytest.fixture
def country() -> CountryData:
    ages = np.arange(N_AGES)

    # Mortality rises with age and falls slowly over time.
    death_rate = 0.00005 * np.exp(0.095 * ages)
    improvement = 0.99 ** np.arange(N_YEARS)
    survival = np.exp(-death_rate[None, None, :] * improvement[:, None, None])
    survival = np.broadcast_to(survival, (N_YEARS, 2, N_AGES)).copy()

    # 1.6 children per woman, spread evenly over ages 20 to 39.
    fertility = np.zeros((N_YEARS, N_AGES))
    fertility[:, 20:40] = 1.6 / 20

    migration = np.zeros((N_YEARS, 2, N_AGES))
    migration[:, :, 20:40] = 50.0

    employment = np.zeros((2, N_AGES))
    employment[:, 20:65] = 0.75

    return CountryData(
        code="TST",
        name="Testland",
        base_year=2025,
        population=np.full((2, N_AGES), 10_000.0) * np.exp(-death_rate.cumsum()),
        survival=survival,
        survival_birth=np.full((N_YEARS, 2), 0.997),
        fertility=fertility,
        migration=migration,
        employment=employment,
        retirement_age=62.0,
        labour_share=0.6,
        pension_spending_gdp=0.14,
        pension_revenue_gdp=0.14,
        indexation="prices",
        wage_growth=0.01,
        interest_rate=0.01,
        history_contribution_rate=np.full(N_HISTORY, 0.14 / 0.6),
        history_wage=1.01 ** np.arange(-N_HISTORY, 0.0),
        history_survival=np.broadcast_to(survival[0], (N_HISTORY, 2, N_AGES)).copy(),
    )
