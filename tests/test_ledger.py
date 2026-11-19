from dataclasses import replace

import numpy as np
import pytest

from pension_simulator.data import CountryData
from pension_simulator.finance import fit_base_year
from pension_simulator.ledger import internal_rate_of_return
from pension_simulator.simulation import Scenario, simulate


def test_internal_rate_of_return() -> None:
    assert internal_rate_of_return(np.array([-1.0, 0.0, 1.21])) == pytest.approx(0.10)
    assert np.isnan(internal_rate_of_return(np.array([-1.0, -1.0])))


def test_ledger_covers_cohorts_from_1960_to_2000(country: CountryData) -> None:
    ledger = simulate(country, Scenario()).ledger
    assert ledger.birth_years[0] == 1960
    assert ledger.birth_years[-1] == 2000


def test_ledger_without_mortality_matches_hand_calculation(country: CountryData) -> None:
    immortal = replace(
        country,
        survival=np.ones_like(country.survival),
        history_survival=np.ones_like(country.history_survival),
    )
    rate, level = fit_base_year(immortal)
    ledger = simulate(immortal, Scenario(indexation="wages")).ledger
    born_2000 = ledger.birth_years == 2000
    # 42 working years from age 20 to 61, at an employment rate of 0.75.
    assert ledger.contributions[born_2000] == pytest.approx(42 * 0.75 * rate)
    # 39 years of pension from age 62 to 100, each at the benefit level.
    assert ledger.pensions[born_2000] == pytest.approx(39 * level)


def test_return_above_prices_exceeds_return_above_wages(country: CountryData) -> None:
    ledger = simulate(country, Scenario()).ledger
    # Wages grow by 1% a year in the test country, so the two units differ by about 1 point.
    gap = ledger.return_above_prices - ledger.return_above_wages
    assert gap == pytest.approx(0.01, abs=0.002)


def test_raising_contributions_lowers_the_return_of_young_cohorts(country: CountryData) -> None:
    borrow = simulate(country, Scenario()).ledger
    balanced = simulate(country, Scenario(balancing_rule="raise_contributions")).ledger
    assert balanced.return_above_wages[-1] < borrow.return_above_wages[-1]
