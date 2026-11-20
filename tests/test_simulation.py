import numpy as np
import pytest

from pension_simulator.data import CountryData
from pension_simulator.finance import BalancingRule
from pension_simulator.simulation import Scenario, simulate


def test_base_year_matches_recorded_shares(country: CountryData) -> None:
    finances = simulate(country, Scenario()).finances
    assert finances.pensions[0] / finances.gdp[0] == pytest.approx(0.14)
    assert finances.contributions[0] / finances.gdp[0] == pytest.approx(0.14)
    assert finances.debt[0] == 0


def test_ageing_country_runs_a_deficit_and_builds_debt(country: CountryData) -> None:
    result = simulate(country, Scenario())
    assert result.first_deficit_year is not None
    assert result.finances.debt[-1] > 0


def test_debt_accumulates_deficits_with_interest(country: CountryData) -> None:
    finances = simulate(country, Scenario(interest_rate=0.03)).finances
    balance = finances.contributions - finances.pensions
    assert finances.debt[11] == pytest.approx(finances.debt[10] * 1.03 - balance[10])


def test_only_population_controls_change_the_population(country: CountryData) -> None:
    # The page reuses the population table of the baseline when fertility, net migration,
    # and the pace of longevity are at their defaults. This holds only while no other
    # control changes the population.
    baseline = simulate(country, Scenario()).population
    other_controls = Scenario(
        retirement_age=70,
        retirement_age_year=2060,
        contribution_rate=0.3,
        benefit_level=0.4,
        balancing_rule="cut_pensions",
        indexation="wages",
        wage_growth=0.03,
        interest_rate=0.05,
    )
    # A new control must be put in one of the two groups, here and in POPULATION_KEYS in app.js.
    population_controls = {"fertility", "net_migration", "longevity_pace"}
    assert set(Scenario.model_fields) == population_controls | other_controls.model_fields_set
    assert (simulate(country, other_controls).population == baseline).all()
    assert (simulate(country, Scenario(fertility=2.5)).population != baseline).any()
    assert (simulate(country, Scenario(net_migration=500_000)).population != baseline).any()
    assert (simulate(country, Scenario(longevity_pace=0.5)).population != baseline).any()


def test_later_retirement_raises_the_support_ratio(country: CountryData) -> None:
    def support_ratio(scenario: Scenario) -> np.ndarray:
        finances = simulate(country, scenario).finances
        return finances.contributors / finances.retirees

    baseline = support_ratio(Scenario())
    later = support_ratio(Scenario(retirement_age=67, retirement_age_year=2035))
    assert later[0] == pytest.approx(baseline[0])
    assert (later[10:] > baseline[10:]).all()


def test_retirement_age_phases_in(country: CountryData) -> None:
    result = simulate(country, Scenario(retirement_age=67, retirement_age_year=2035))
    assert result.retirement_age[0] == 62
    assert result.retirement_age[5] == pytest.approx(64.5)
    assert result.retirement_age[10:] == pytest.approx(67)


@pytest.mark.parametrize("rule", ["raise_contributions", "cut_pensions"])
def test_balancing_rules_remove_the_deficit(country: CountryData, rule: BalancingRule) -> None:
    finances = simulate(country, Scenario(balancing_rule=rule)).finances
    balance = finances.contributions - finances.pensions
    assert balance.min() == pytest.approx(0, abs=1e-6)
    assert finances.debt.max() <= 1e-6


def test_raising_contributions_never_lowers_the_rate(country: CountryData) -> None:
    finances = simulate(country, Scenario(balancing_rule="raise_contributions")).finances
    assert (finances.contribution_rate >= finances.contribution_rate[0] - 1e-12).all()
    assert finances.contribution_rate.max() > finances.contribution_rate[0]


def test_wage_indexation_costs_more_than_price_indexation(country: CountryData) -> None:
    prices = simulate(country, Scenario(indexation="prices")).finances
    wages = simulate(country, Scenario(indexation="wages")).finances
    # The rule applies from the base year onward, so the base year is the same.
    assert wages.pensions[0] == pytest.approx(prices.pensions[0])
    assert wages.pensions[30] > prices.pensions[30]


def test_first_deficit_year_is_the_same_under_every_rule(country: CountryData) -> None:
    years = {
        simulate(country, Scenario(balancing_rule=rule)).first_deficit_year
        for rule in ("borrow", "cut_pensions")
    }
    assert len(years) == 1
