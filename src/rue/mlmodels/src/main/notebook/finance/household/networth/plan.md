# networth

The plan for the `finance_household_networth` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/networth/notebook.ipynb` |
| **Registered Model** | `finance_household_networth` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2), target `local` |

**Status, 2026-11-05.** A placeholder. The notebook fits on a synthetic series, packages a `static` project, replays the golden and records it; the real series is not loaded yet and nothing is released.

## Intent

Track the household's balance sheet and savings rate against the plan: the starting wealth the portfolio models need, how fast it is growing, and whether the actual path is tracking the base scenario. It closes the loop between the forecasts and what happens.

## What the data holds

The `Bank` workbook that `wrangle`'s `bank` plugin writes (tabs `Accounts`, `Classifier`, `Balances`, `Transactions_<year>` and the `Summary` and `Logs` outputs), on Drive under `Wrangle/Bank/release/data`. About 11,700 transactions across 13 accounts from 2021-05-01, when the statement history begins, to now, each with a `Category` (about 40) that the `Classifier` tab maps to a bucket. `bank` writes nothing to Postgres yet, so the first change for every household project is a `bank` table in `wrangle`'s schema, or a loader that reads the year files. The `Balances` tab holds a reading per account over time (linked accounts three-hourly, manual ones monthly), so assets and liabilities by account are available from 2021-05, including the share accounts (`BWA`, `CBA`, `HSBC`, `AMEX`, `QAN`). Investments are in the `equity` table and the Portfolio sheet.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_household_networth_in` | FP64 | Unused, required by the spec so the request is still validated |
| Output | `finance_household_networth_current_dollars` | FP64 | Net worth at the latest month end, dollars. |
| Output | `finance_household_networth_savings_rate_pct` | FP64 | Share of income not spent over the period, percent. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell.

## Approach

1. **Explore** the balance sheet by account type and the monthly change, and reconcile it to income less spending: the **savings rate** is the change in net worth less market gains, divided by income.
2. **Separate saving from market return.** Net worth growth is saving plus the return on the invested part, and the plan tests each against its own forecast (`household/costs`, `portfolio/returns`).
3. **Tracking.** Compare actual net worth with the base, low and high paths from today's date, as a **fan chart**; a path outside the fan is the early warning.
4. **Ship** the current net worth, savings rate and a tracking signal.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Property, super and other non-bank assets with dated values | Net worth is incomplete without them | Manual balances in the `Balances` tab |
| Liabilities and their rates | Debt changes the safe risky share | `Accounts` and `Balances` |

## To do

1. Add a `bank` table to `wrangle`.
2. Build the net worth series and reconcile it to income less spending.
3. Add the tracking fan once `portfolio/returns` is real.
