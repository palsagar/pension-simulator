# Pension Simulator

An educational simulator of pay-as-you-go pension systems. It projects a country's population by age and shows how the pension system's finances respond to the retirement age and other assumptions.

## Language

### The pension system

**Pay-as-you-go pension system**:
A public pension scheme in which the pensions of today's **Retirees** are paid directly from the contributions of today's **Contributors**, with no invested fund behind them.
_Avoid_: Ponzi scheme (allowed as informal wording in the user interface only), state pension fund

**Contributor**:
A person of working age who is employed and pays pension contributions in a given year.
_Avoid_: Worker, taxpayer, active

**Retiree**:
A person at or above the **Retirement age**, who receives a pension.
_Avoid_: Pensioner, recipient, beneficiary

**Retirement age**:
The age at which a person stops being a potential **Contributor** and becomes a **Retiree**.

**Support ratio**:
The number of **Contributors** divided by the number of **Retirees** in a given year.
_Avoid_: Dependency ratio (it is the inverse and counts by age only), contributor-to-recipient ratio

**Contribution rate**:
The fraction of the average wage that each **Contributor** pays into the pension system.

**Benefit level**:
The average pension divided by the average wage.
_Avoid_: Replacement rate (that term compares a person's pension to their own last wage)

**Pension indexation**:
The rule by which a pension rises after it is first awarded: with wages, or with prices only. Under price indexation, a pension falls behind the average wage as the **Retiree** ages.
_Avoid_: Revaluation, uprating

### The finances

**Annual balance**:
Contributions received minus pensions paid in one year. A negative value is an annual deficit.

**Pension debt**:
The accumulated sum of past annual deficits plus interest, covering the pension system alone and not the whole government budget.
_Avoid_: Bankruptcy, government debt, bank balance

**Balancing rule**:
The choice of who pays for an annual deficit: borrowing (adds to **Pension debt**), a higher **Contribution rate**, or a lower **Benefit level**.
_Avoid_: Closure rule, adjustment mechanism

### The generations

**Lifetime ledger**:
For one **Cohort**, the total contributions paid and the total pensions received over a whole life, both measured in years of average wage.
_Avoid_: Generational account

**Internal rate of return**:
The yearly rate of return, above price inflation, that a **Cohort** earns on its contributions through the pensions it later receives.
_Avoid_: Yield, recovery rate

### The population

**Cohort**:
All people born in the same year. A cohort ages one year per year and shrinks through death and changes through migration.

## Example dialogue

> **Dev:** When the user raises the **Retirement age** from 62 to 65, what changes?
> **Domain expert:** Three **Cohorts** move from being **Retirees** back to being potential **Contributors**. The **Support ratio** rises on both sides of the fraction.
> **Dev:** So the **Annual balance** improves at once. Does the system go bankrupt if it stays negative?
> **Domain expert:** We do not say bankrupt. The state covers the gap, and the gap accumulates with interest as **Pension debt**.
> **Dev:** And the **Benefit level** is what a retiree gets compared to their own last salary?
> **Domain expert:** No, that is the replacement rate. The **Benefit level** is the average pension over the average wage across the whole country.
