# lumps

The plan for the `finance_household_lumps` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/lumps/notebook.ipynb` |
| **Registered Model** | `finance_household_lumps` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2), target `local` |

**Status, 2026-11-05.** A placeholder. The notebook fits on a synthetic series, packages a `static` project, replays the golden and records it; the real series is not loaded yet and nothing is released.

## Intent

Model the lumpy spending that a smooth growth rate hides: home improvements, car replacement, school fees, holidays, tax and insurance premiums. A Monte Carlo that ignores lumps understates the chance of a bad year, and a sinking fund needs a schedule.

## What the data holds

The `Bank` workbook that `wrangle`'s `bank` plugin writes (tabs `Accounts`, `Classifier`, `Balances`, `Transactions_<year>` and the `Summary` and `Logs` outputs), on Drive under `Wrangle/Bank/release/data`. About 11,700 transactions across 13 accounts from 2021-05-01, when the statement history begins, to now, each with a `Category` (about 40) that the `Classifier` tab maps to a bucket. `bank` writes nothing to Postgres yet, so the first change for every household project is a `bank` table in `wrangle`'s schema, or a loader that reads the year files. The large irregular categories are home improvements, car costs, school, holidays, income tax and shire rates; each has a date and an amount.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_household_lumps_in` | FP64 | Unused, required by the spec so the request is still validated |
| Output | `finance_household_lumps_expected_annual_dollars` | FP64 | Expected annual spend on irregular expenses, dollars. |
| Output | `finance_household_lumps_p95_annual_dollars` | FP64 | Annual spend on irregular expenses that is exceeded one year in twenty, dollars. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell.

## Approach

1. **Explore** the distribution of amounts per category: how many a year, how large, how skewed. A heavy tailed amount is a **lognormal** or a **Pareto** tail; a count a year is a **Poisson** process.
2. **Fit a compound Poisson** per category (a rate of events a year and an amount distribution), which is the standard model for lumpy costs and can be simulated directly in `portfolio/montecarlo`.
3. **Known schedules** (a car at an age, a roof at a life) are deterministic items with a date range, kept apart from the random ones.
4. **Ship** the expected annual lump and its 95th percentile.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Ages and replacement cycles of the house, cars and appliances | The deterministic schedule | A list in the notebook |
| Insurance quotes and rates notices | Known annual lumps | Statements |

## To do

1. Pull the category amounts and plot them.
2. Fit the compound Poisson per category and check it against the largest year seen.
