# rates

The plan for the `finance_economy_rates` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `economy` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/economy/rates/notebook.ipynb` |
| **Registered Model** | `finance_economy_rates` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2), served by `mlserver` |

**Status, 2026-11-05.** A placeholder beside the other finance projects. The notebook, the directories and this plan are scaffolded; nothing is fitted or built.

## Intent

Give one annual no risk (bank) rate to 2070 and the matching real return, so the floor of every return scenario and the discount rate of every spending annuity come from one place. `portfolio/returns` and `portfolio/spending` use it.

## What the data holds

The `interest` table in `wrangle`'s Postgres, entities `Bank` (the no risk rate), `Inflation` and `Net` (the real return of cash), each as the mean over 1, 5, 10, 20 and 40 years, from the Reserve Bank `f04hist` table (retail rates) and the `Rates` sheet.

## Approach

1. **Look at the term structure of the windows.** `Bank` at 5, 10, 20 and 40 years shows the regimes, and `Net` shows that the real return of cash has been far smaller and far less stable than the nominal one.
2. **Model the real rate, not the nominal.** The real cash rate is the steadier series, so model `Net` as mean reverting and add inflation from `economy/inflation` to get the nominal. This keeps the two forecasts consistent by construction (Fisher relation).
3. **Simulate** the pair and take compound rates, low, base and high as percentiles.
4. **Ship** the nominal and the real rates.

Placeholder: low, base and high are the 40, 10 and 5 year `Bank` means ordered, until step 3.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Index linked government bond yields | The market's real riskless rate, a better anchor than cash | Reserve Bank |
| Term deposit and offset rates actually available to you | The rate you really earn, net of the bank's margin | Your accounts, `Bank` workbook interest rows |

## To do

1. Add `query_postgres` and read the `Bank` and `Net` windows.
2. Compare the cash rate you earn (interest rows in the `Bank` workbook) with the published one.
3. Fit and write the golden samples.
