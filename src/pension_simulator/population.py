"""Population projection by the cohort-component method.

The mathematics is stated in ``docs/model.md``, section 1. Array conventions are
described in :mod:`pension_simulator.data`.
"""

import numpy as np

SHARE_OF_BIRTHS = np.array([0.488, 0.512])  # women, men
FERTILITY_TARGET_YEAR = 2040


def adjust_survival(survival: np.ndarray, pace: float) -> np.ndarray:
    """Scale the improvement in mortality after the base year.

    Parameters
    ----------
    survival : np.ndarray
        Yearly survival probabilities. The first axis is the year.
    pace : float
        Share of the baseline improvement that takes place. A pace of 0 freezes
        mortality at its base-year level. A pace of 1 returns the baseline.

    Returns
    -------
    np.ndarray
        Adjusted survival probabilities, with the shape of ``survival``.

    Examples
    --------
    .. code-block:: python

        frozen = adjust_survival(country.survival, pace=0.0)
    """
    death_rate = -np.log(survival)
    # Interpolate between the base-year death rate and the baseline one on a log scale.
    adjusted = death_rate[0] ** (1 - pace) * death_rate**pace
    return np.exp(-adjusted)


def adjust_fertility(fertility: np.ndarray, base_year: int, target: float) -> np.ndarray:
    """Move the number of children per woman to a target value.

    The number moves in a straight line from its baseline value in the base year
    to ``target`` in 2040. After 2040 it follows the baseline trend from that level.

    Parameters
    ----------
    fertility : np.ndarray
        Baseline fertility rates of shape ``[T, 101]``.
    base_year : int
        Calendar year of index 0.
    target : float
        Target number of children per woman in 2040.

    Returns
    -------
    np.ndarray
        Adjusted fertility rates of shape ``[T, 101]``.

    Examples
    --------
    .. code-block:: python

        higher = adjust_fertility(country.fertility, country.base_year, target=2.1)
    """
    years = base_year + np.arange(len(fertility))
    progress = np.clip((years - base_year) / (FERTILITY_TARGET_YEAR - base_year), 0, 1)
    baseline_in_target_year = fertility[FERTILITY_TARGET_YEAR - base_year].sum()
    # The age pattern of mothers is kept. Only the level changes. A target equal
    # to the baseline value of 2040 leaves the baseline unchanged in every year.
    factor = 1 + progress * (target / baseline_in_target_year - 1)
    return fertility * factor[:, None]


def adjust_migration(migration: np.ndarray, total: float) -> np.ndarray:
    """Rescale net migration to a chosen yearly average.

    Every year is scaled by the same factor, so the baseline pattern over time,
    age, and sex is kept.

    Parameters
    ----------
    migration : np.ndarray
        Baseline net migrants of shape ``[T, 2, 101]``.
    total : float
        Net migrants per year, summed over ages and sexes and averaged over all years.

    Returns
    -------
    np.ndarray
        Net migrants of shape ``[T, 2, 101]``.

    Examples
    --------
    .. code-block:: python

        closed_borders = adjust_migration(country.migration, total=0.0)
    """
    baseline_average = migration.sum() / len(migration)
    return migration * (total / baseline_average)


def project(
    population: np.ndarray,
    survival: np.ndarray,
    survival_birth: np.ndarray,
    fertility: np.ndarray,
    migration: np.ndarray,
) -> np.ndarray:
    """Project the population one year at a time.

    Parameters
    ----------
    population : np.ndarray
        People at the start of the base year, of shape ``[2, 101]``.
    survival : np.ndarray
        Yearly survival probabilities of shape ``[T, 2, 101]``.
    survival_birth : np.ndarray
        Probability that a newborn survives the calendar year, of shape ``[T, 2]``.
    fertility : np.ndarray
        Births per woman per year by age of mother, of shape ``[T, 101]``.
    migration : np.ndarray
        Net migrants by age at the end of the year, of shape ``[T, 2, 101]``.

    Returns
    -------
    np.ndarray
        Population of shape ``[T + 1, 2, 101]``. Index 0 is the base year.

    Examples
    --------
    .. code-block:: python

        population = project(
            country.population,
            country.survival,
            country.survival_birth,
            country.fertility,
            country.migration,
        )
    """
    n_years = len(survival)
    result = np.empty((n_years + 1, *population.shape))
    result[0] = population
    for t in range(n_years):
        now = result[t]
        nxt = result[t + 1]
        survivors = now * survival[t]

        # Every cohort moves up one age. The last group also keeps its own survivors.
        nxt[:, 1:] = survivors[:, :-1]
        nxt[:, -1] += survivors[:, -1]
        nxt[:, 1:] += migration[t][:, 1:]

        # Births come from the average number of women alive during the year.
        # Age 0 is left out: it is not filled yet, and newborns have no children.
        women = (now[0, 1:] + nxt[0, 1:]) / 2
        births = (fertility[t, 1:] * women).sum()
        nxt[:, 0] = births * SHARE_OF_BIRTHS * survival_birth[t] + migration[t][:, 0]
    return result
