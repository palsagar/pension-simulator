"""Checks on the committed data files of the real countries."""

from pathlib import Path

import numpy as np
import pytest

from pension_simulator.api import country_defaults
from pension_simulator.data import CountryData, load_country
from pension_simulator.simulation import Scenario, simulate

DATA_DIR = Path(__file__).parents[1] / "data" / "countries"


@pytest.fixture(params=["DEU", "ESP", "FRA", "ITA"])
def real_country(request: pytest.FixtureRequest) -> CountryData:
    return load_country(DATA_DIR / f"{request.param}.npz")


def test_baseline_starts_at_recorded_spending(real_country: CountryData) -> None:
    finances = simulate(real_country, Scenario()).finances
    assert finances.pensions[0] / finances.gdp[0] == pytest.approx(
        real_country.pension_spending_gdp
    )
    assert finances.debt[0] == 0


def test_baseline_is_complete_and_finite(real_country: CountryData) -> None:
    result = simulate(real_country, Scenario())
    assert result.years[0] == 2025 and result.years[-1] == 2100
    assert (result.population >= 0).all()
    assert np.isfinite(result.finances.debt).all()
    assert np.isfinite(result.ledger.return_above_wages).all()


def test_support_ratio_falls_by_2050(real_country: CountryData) -> None:
    finances = simulate(real_country, Scenario()).finances
    support_ratio = finances.contributors / finances.retirees
    assert support_ratio[25] < support_ratio[0]


def test_default_controls_reproduce_the_baseline(real_country: CountryData) -> None:
    baseline = simulate(real_country, Scenario())
    explicit = simulate(real_country, country_defaults(real_country))
    assert explicit.population == pytest.approx(baseline.population)
    assert explicit.finances.debt == pytest.approx(baseline.finances.debt)
