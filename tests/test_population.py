import numpy as np
import pytest

from pension_simulator.data import CountryData
from pension_simulator.population import (
    adjust_fertility,
    adjust_migration,
    adjust_survival,
    project,
)


def run(country: CountryData, **overrides: np.ndarray) -> np.ndarray:
    rates = {
        "survival": country.survival,
        "survival_birth": country.survival_birth,
        "fertility": country.fertility,
        "migration": country.migration,
    }
    return project(country.population, **(rates | overrides))


def test_population_is_constant_without_births_deaths_or_migration(country: CountryData) -> None:
    population = run(
        country,
        survival=np.ones_like(country.survival),
        fertility=np.zeros_like(country.fertility),
        migration=np.zeros_like(country.migration),
    )
    assert population.sum(axis=(1, 2)) == pytest.approx(country.population.sum())


def test_cohort_moves_up_one_age_per_year(country: CountryData) -> None:
    population = run(country, migration=np.zeros_like(country.migration))
    expected = country.population[:, 30] * country.survival[0, :, 30]
    assert population[1, :, 31] == pytest.approx(expected)


def test_births_follow_fertility(country: CountryData) -> None:
    population = run(country)
    women = (population[0, 0, 20:40] + population[1, 0, 20:40]) / 2
    births = (women * 1.6 / 20).sum()
    assert population[1, :, 0].sum() == pytest.approx(births * 0.997)


def test_migrants_are_added(country: CountryData) -> None:
    with_migration = run(country)
    without = run(country, migration=np.zeros_like(country.migration))
    assert (with_migration[1] - without[1])[:, 25] == pytest.approx([50.0, 50.0])


def test_longevity_pace(country: CountryData) -> None:
    assert adjust_survival(country.survival, 1.0) == pytest.approx(country.survival)
    frozen = adjust_survival(country.survival, 0.0)
    assert frozen[-1] == pytest.approx(country.survival[0])
    # A faster pace means more survivors than the baseline in later years.
    assert (adjust_survival(country.survival, 1.5)[-1] > country.survival[-1]).all()


def test_fertility_reaches_target_in_2040_and_holds(country: CountryData) -> None:
    adjusted = adjust_fertility(country.fertility, country.base_year, target=2.1)
    children = adjusted.sum(axis=1)
    assert children[0] == pytest.approx(1.6)
    assert children[2040 - 2025 :] == pytest.approx(2.1)


def test_migration_is_rescaled_to_total(country: CountryData) -> None:
    adjusted = adjust_migration(country.migration, total=10_000)
    assert adjusted.sum(axis=(1, 2)) == pytest.approx(10_000)
