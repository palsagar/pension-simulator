# Modelling choices

This document records the choices behind the model: what it assumes, where its numbers come from, and how its results should be read. The mathematics is in [`model.md`](model.md). The vocabulary is in [`CONTEXT.md`](../CONTEXT.md).

## How to read the results

The baseline is a "nothing changes" scenario. It is not a forecast.

The model holds three things fixed that official projections let move:

- the benefit level of newly awarded pensions;
- the employment rates by age;
- the retirement age, unless the user changes it.

Official projections, such as the European Commission's Ageing Report, include reforms that are already in law: later retirement ages, lower future pension rights, and rising employment of older workers. For this reason the baseline of the simulator is much more pessimistic than official projections.

| Country | Support ratio 2025 | Support ratio 2050 | Pension spending 2025 (% of GDP) | Pension spending 2050 (% of GDP) | Pension debt 2050 (% of GDP) |
|---|---|---|---|---|---|
| France | 1.64 | 1.30 | 13.4 | 16.3 | 51 |
| Germany | 2.25 | 1.53 | 10.8 | 15.9 | 92 |
| Spain | 2.30 | 1.06 | 12.3 | 26.2 | 181 |
| Italy | 1.79 | 0.97 | 16.1 | 29.3 | 198 |

These are the baseline results with all default values. The values come from the country files built in November 2026, and they change when the data is rebuilt.

## Scope

- **Purpose.** The simulator is educational. It is simple and transparent, and it starts from recorded data.
- **Countries.** France, Germany, Italy, and Spain. A country is one data file, so a new country needs no change to the model.
- **System.** The model covers the public pension system alone, not the whole government budget.
- **Time span.** The simulation runs from 2025 to 2100. The yearly charts are meant to show 2025 to 2050 by default. The model always computes to 2100, because a person born in 1990 draws a pension until about 2085.
- **Direction of effects.** Population drives finances. Finances do not change births, deaths, migration, or employment. Such feedback exists in reality, but its size is contested and hard to fit to data.

## Population

- **Method.** The model moves each cohort up one age per year. This is exact on a one-year grid. See [ADR 0001](adr/0001-annual-cohort-steps-instead-of-an-ode-solver.md).
- **Detail.** Ages 0 to 100 in one-year groups, for women and men separately. The last group holds everyone aged 100 or more.
- **Baseline.** Population, mortality, and fertility come from the medium projection of the United Nations World Population Prospects 2024.
- **Survival.** The survival probability from age `x` to age `x + 1` is the ratio of the life-table person-years `L(x+1) / L(x)`.
- **Migration by age.** The United Nations publishes net migration as a yearly total only. The model derives migrants by age and sex as the population change that survival and births do not explain. With this choice the model reproduces the United Nations projection exactly at default values.
- **Check on migration.** The data build compares the derived migration with the published yearly totals, and fails if the averages differ by more than 2%. The current difference is below 1.6% for every country.

### Population controls

- **Fertility.** The user sets the number of children per woman in 2040. The level moves in a straight line from the 2025 baseline to that value. After 2040, fertility follows the United Nations trend from the new level.
- **Net migration.** The user sets the average number of net migrants per year over the simulation. The baseline is multiplied by one factor in all years, so its pattern over time, age, and sex is kept.
- **Longevity pace.** The user sets the share of the projected fall in mortality that takes place, from 0% (mortality frozen at the 2025 level) to 150%.

The default value of each control reproduces the baseline exactly. The fertility and migration controls are defined as they are for this reason. The baseline of Germany, for example, has negative net migration in 2025 and positive net migration later, so a control that fixed one number for every year could not reproduce it.

## Finances

- **Units.** All amounts are in constant euros, so inflation does not appear. Results are shares of GDP.
- **GDP.** GDP is the total wage bill divided by the labour share of income. The labour share is fixed per country.
- **Retirement.** Everyone at or above the retirement age counts as a retiree and receives a pension. Everyone below it works at the employment rate of their age and sex.
- **Later retirement.** When the retirement age rises, people in the newly added working ages get the employment rate of the 55-to-59 age group of that country. The new age phases in on a straight line up to a target year.
- **Benefit level.** The control sets the level of a newly awarded pension, as a share of the average wage of that year. The reported benefit level is the average over all retirees, which is lower under price indexation.
- **Pension indexation.** Under price indexation, a pension stays constant in purchasing power after it is awarded. Under wage indexation, it follows the average wage. Each country defaults to its own rule. The rule that the user selects applies from 2025 onward.
- **Balancing rule.** An annual deficit is covered by borrowing, by a higher contribution rate, or by a lower benefit level. The last two act only in years that would be in deficit. The first deficit year is measured before the rule acts.

### The base year

The model is fitted so that 2025 matches recorded data:

- The benefit level is set so that pension spending equals the recorded share of GDP.
- The contribution rate is set so that revenue equals spending.

Each country therefore starts balanced, and the simulation shows only the gap that demographic change opens. The fitted contribution rate is an effective rate. It includes earmarked taxes and state transfers, and it is higher than the payroll rate in law. See [ADR 0002](adr/0002-base-year-revenue-includes-all-current-funding.md).

## Generations

- **Representative person.** The lifetime ledger follows one person born in the country, from age 20 to age 100. The person is the average of a woman and a man, works at the employment rates by age, and faces the survival chances of their cohort.
- **Cohorts covered.** Cohorts born from 1960 to 2000. The first limit comes from the data: recorded pension spending starts in 1980, when the 1960 cohort was 20. The second limit comes from the end of the simulation in 2100.
- **Two units of return.** The internal rate of return is reported above wage growth and above price inflation. The French Conseil d'orientation des retraites uses the rate above wage growth as its headline figure.
- **Reading the return under borrowing.** Under the "borrow" rule, part of the cost of pensions sits in the pension debt and is charged to no cohort. The return under that rule must be read together with the pension debt.

## Data sources

| Input | Source | Detail |
|---|---|---|
| Population, mortality, fertility, net migration totals | United Nations World Population Prospects 2024 | Medium projection, single years of age. Licence CC BY 3.0 IGO. |
| Employment rates by age and sex | OECD labour force statistics | Five-year age groups, latest year. Every age in a group takes the rate of the group. |
| Pension spending | OECD Social Expenditure database | Public spending on old-age and survivors cash benefits, share of GDP, from 1980. |
| Labour share | European Commission AMECO database, series `ALCD0` | Adjusted wage share, share of GDP at market prices. |
| Past wages | European Commission AMECO database, series `RWCDC` | Real compensation per employee, deflated by consumer prices. |

The script [`scripts/build_country_data.py`](../scripts/build_country_data.py) downloads these sources and writes the country files. The running service reads only the country files.

## Values chosen by hand

No dataset supplies these values in a usable form.

| Value | France | Germany | Italy | Spain |
|---|---|---|---|---|
| Retirement age in 2025 | 62.75 | 66.17 | 67.0 | 66.67 |
| Pension indexation | prices | wages | prices | prices |

For Germany, Italy, and Spain, the value is the standard retirement age in law for a person who retires in 2025. For France, the value is the minimum legal age, which is 62 years and 9 months. Most people in France retire at this age. The French age for a full pension without conditions is 67. This difference in concept is a limit on comparing the countries.

Two defaults apply to every country: wages grow by 1% a year above inflation, and pension debt carries 1.5% interest a year above inflation. The user can change both.

## Simplifications

- **Sharp retirement age.** In reality people retire over a range of ages, and many retire before the standard age. The fitted benefit level absorbs this difference in the base year.
- **No country-specific rules.** The model has no contribution quarters (France), pension points (Germany), or notional accounts (Italy).
- **German indexation.** German law indexes pensions to wages minus a sustainability correction. The model uses plain wage indexation.
- **Italian indexation.** Italian law indexes high pensions below price inflation. The model uses plain price indexation.
- **Pension spending year.** The latest recorded year is 2021 or 2022. The model uses it for 2025.
- **One kind of pension.** Recorded spending includes survivor pensions. The model pays all of it to people above the retirement age.
- **No differences between people.** Everyone of the same age and sex has the same wage, the same employment rate, and the same pension.
- **History in the lifetime ledger.** For the years before 2025, the ledger uses today's employment rates by age, and it assumes that revenue matched spending in each year. Germany before 1991 takes the labour share of West Germany.
- **Pensions before 2025.** The few pensions that the 1960 to 1962 cohorts drew before 2025 take the 2025 level.

## Comparison with official French figures

The Conseil d'orientation des retraites publishes an internal rate of return for one typical case: a private-sector employee with a full career. Its June 2026 report gives the following values. The return above wage growth is in Part 3, Chapter 1, Figure 3.7, and the return above price inflation is in the methodological annex, Figure A2.13.

| Cohort | Return above wage growth | Return above price inflation |
|---|---|---|
| 1950 | 1.77% | 2.32% |
| 1990 | 0.80% | 1.47% |

For the 1990 cohort in France, the simulator gives a return above wage growth of 0.63% under the "borrow" rule and 0.37% under the "raise contributions" rule. The two sources are not directly comparable. The official figure follows one typical career under the rules in law. The simulator follows an average person, with employment below 100% and with the cost of ageing charged through the balancing rule.
