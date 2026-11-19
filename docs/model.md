# The model

This document states the mathematics of the simulator. The vocabulary is defined in [`CONTEXT.md`](../CONTEXT.md). The reasons for the less obvious choices are in [`docs/adr/`](adr/).

The model has three parts. The population part projects how many people of each age are alive in each year. The finance part turns that population into contributions, pensions, and pension debt. The generational part follows one birth cohort through its life and measures what it pays and what it receives.

Information flows one way: population drives finances. Finances do not change births, deaths, migration, or employment.

## 1. Population

### Continuous form

Let `n(a, t)` be the number of people of age `a` at time `t`. The McKendrick–von Foerster equation describes how it changes:

```
∂n/∂t + ∂n/∂a = −μ(a,t)·n(a,t) + m(a,t)
n(0, t) = ∫ f(a,t)·n_women(a,t) da
```

- `μ(a,t)` is the death rate at age `a`.
- `m(a,t)` is net migration at age `a` (arrivals minus departures).
- `f(a,t)` is the fertility rate of women of age `a`.

### Discrete form used in the code

The state is `N[s, a, t]`: the number of people of sex `s` and age `a` at the start of year `t`. Ages run from 0 to 100, and the last group holds everyone aged 100 or more. The model advances one year at a time:

```
N[s, a+1, t+1] = N[s, a, t] · S[s, a, t] + M[s, a+1, t]          for a = 0 … 98
N[s, 100, t+1] = (N[s, 99, t] · S[s, 99, t]) + (N[s, 100, t] · S[s, 100, t]) + M[s, 100, t]
```

- `S[s, a, t]` is the probability that a person of sex `s` and age `a` survives the year.
- `M[s, a, t]` is the net number of migrants of sex `s` who are age `a` at the end of the year.

Births during year `t` come from the women alive during that year:

```
B(t) = Σ_a  F[a, t] · ( N[women, a, t] + N[women, a, t+1] ) / 2
N[s, 0, t+1] = B(t) · share_s · S_birth[s, t] + M[s, 0, t]
```

`share_s` is the share of births of each sex (about 0.512 boys). `S_birth` is the probability that a newborn survives to the end of the calendar year.

The baseline values of `S` and `F` come from the United Nations medium projection. The United Nations publishes net migration as a yearly total only, so `M` by age and sex is derived as a residual: the projected population of each age, minus the survivors of the population one year younger in the year before. With these values the model must reproduce the United Nations population projection to within 1% in every year to 2100. An automated test enforces this.

### User controls on the population

| Control | Effect |
|---|---|
| Fertility | The user sets a target number of children per woman. Every `F[a, t]` is multiplied by a factor that moves in a straight line from 1 in 2025 to the value that gives the target in 2040. The factor then stays fixed, so fertility follows the United Nations trend from the new level. |
| Net migration | The user sets the average number of people per year over the simulation. The baseline is multiplied by one factor in all years, so its pattern over time, age, and sex is kept. |
| Longevity pace | The user sets a pace `p` between 0 and 1.5. The death rate becomes `log μ'(a,t) = log μ(a,2025) + p · ( log μ(a,t) − log μ(a,2025) )`. A pace of 0 freezes mortality at its 2025 level. A pace of 1 is the United Nations projection. |

## 2. Finances

All money amounts are in constant euros, so inflation does not appear.

### Contributors and retirees

`R(t)` is the retirement age in year `t`. The user sets a target age and a target year, and `R(t)` moves in a straight line from the current age to the target. `e[s, a]` is the employment rate of sex `s` at age `a`.

```
Contributors  W(t) = Σ_s Σ_{a < R(t)}  e[s, a] · N[s, a, t]
Retirees      P(t) = Σ_s Σ_{a ≥ R(t)}  N[s, a, t]
Support ratio      = W(t) / P(t)
```

When `R(t)` is not a whole number, the age group that contains it is split in proportion. When the retirement age rises above its current value, people in the newly added working ages get the employment rate of the 55-to-59 age group of that country.

### Wages and GDP

The average wage grows at a constant productivity rate `g`. GDP is the total wage bill divided by the labour share `λ`, a fixed number per country near 0.6.

```
w(t)   = w(2025) · (1 + g)^(t − 2025)
GDP(t) = w(t) · W(t) / λ
```

### Contributions and pensions

`τ(t)` is the contribution rate. `ρ` is the benefit level of a newly awarded pension: the first pension of a new retiree divided by the average wage of that year. Under price indexation, the benefit level across all retirees is lower than `ρ`, because older pensions have fallen behind wages.

```
Contributions  C(t) = τ(t) · w(t) · W(t)
Pensions       B(t) = Σ_s Σ_{a ≥ R(t)}  N[s, a, t] · b(a, t)
```

`b(a, t)` is the pension of a retiree of age `a` in year `t`. It depends on the pension indexation rule:

- **Wage indexation:** `b(a, t) = κ(t) · ρ · w(t)`. Every pension follows the current average wage.
- **Price indexation:** `b(a, t) = κ(t) · ρ · w(t_award)`, where `t_award` is the year in which that cohort reached the retirement age. The pension then stays constant in purchasing power and falls behind wages.

`κ(t)` is a scaling factor that equals 1 unless the balancing rule "cut pensions" is active.

Pensions already being paid in 2025 start from the level that the country's own rule implies. The rule that the user selects applies from 2025 onward.

### Balance and debt

```
Annual balance  A(t)   = C(t) − B(t)
Pension debt    D(t+1) = D(t) · (1 + r) − A(t)          with D(2025) = 0
```

`r` is the interest rate above inflation. The results are reported as shares of GDP. The first deficit year is the first year in which `A(t)` is negative.

### Balancing rule

| Rule | What the model does each year |
|---|---|
| Borrow (default) | `τ` and `κ` stay fixed. The deficit adds to pension debt. |
| Raise contributions | In a year that would be in deficit, `τ(t) = B(t) / ( w(t) · W(t) )`. The annual balance is zero. |
| Cut pensions | In a year that would be in deficit, `κ(t) = C(t) / B(t)`. The annual balance is zero. |

The first deficit year is measured before the balancing rule acts, so it is the same under all three rules.

### Fitting the base year

For each country, two numbers are fitted so that the model matches recorded data in 2025:

- `ρ` is set so that `B(2025) / GDP(2025)` equals recorded public pension spending as a share of GDP.
- `τ` is set so that `C(2025)` equals recorded pension-system revenue from all sources.

The fitted `τ` is an effective rate. It is higher than the payroll rate written in law, because it includes earmarked taxes and state transfers. See [ADR 0002](adr/0002-base-year-revenue-includes-all-current-funding.md).

## 3. Generations

The lifetime ledger follows a representative person born in the country in year `c`. This person works at the employment rates of their time and faces the survival chances of their cohort. Let `l_c(a)` be the probability that the person is alive at age `a`, given that they were alive at age 20. The figures average over both sexes.

```
Lifetime contributions = Σ_{a < R}  l_c(a) · e(a) · τ(c + a)                   (in years of average wage)
Lifetime pensions      = Σ_{a ≥ R}  l_c(a) · b(a, c + a) / w(c + a)             (in years of average wage)
```

The internal rate of return is the rate `i` at which the person's payments and receipts, in constant euros, cancel out:

```
Σ_a  l_c(a) · [ pension(a) − contribution(a) ] / (1 + i)^a  =  0
```

The model reports this rate in two units. The rate above price inflation uses amounts in constant euros, as in the formula above. The rate above wage growth uses amounts in years of average wage, so it removes the effect of economic growth and compares cohorts on equal terms. The French Conseil d'orientation des retraites publishes both, and its headline figure is the rate above wage growth.

Years before 2025 use recorded data: the recorded population, and a contribution rate and benefit level fitted to recorded pension spending in each past year. Recorded pension spending starts in 1980 for all four countries, so the ledger covers cohorts born from 1960. Years from 2025 use the simulation. The model always computes to 2100, so that cohorts who retire after 2050 have a complete ledger.

The ledger makes two simplifications for the years before 2025. Employment rates by age take their current values. Revenue is assumed to have matched spending in each past year, so the past contribution rate is recorded pension spending divided by the wage bill.

Under the "borrow" balancing rule, part of the cost of pensions sits in the pension debt and is charged to no cohort. The internal rate of return under that rule must be read together with the pension debt.

## 4. What the model leaves out

- Country-specific pension rules, such as contribution quarters in France or pension points in Germany.
- Any effect of contribution rates or pension levels on employment, migration, or births.
- Survivor pensions, disability pensions, and differences in wages between people.
- The rest of the government budget.
