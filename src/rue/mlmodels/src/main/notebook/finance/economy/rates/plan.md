# rates

The plan for the `finance_economy_rates` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `economy` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/economy/rates/notebook.ipynb` |
| **Registered Model** | `finance_economy_rates` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2), target `served` |

**Status, 2026-11-05.** A placeholder. The notebook fits on a synthetic series, packages a `static` project, replays the golden and records it; the real series is not loaded yet and nothing is released.

## Intent

Give the economy's inflation rate, the risk-free (bank) rate and the real return of cash to 2070, each as a low, base and high scenario, so the floor of every return scenario, the discount rate of every withdrawal and the inflation component of household costs come from one place. They come from one table, the Reserve Bank's `interest` series, and satisfy real = risk-free less inflation, so the three cannot disagree. `household/costs` adds its own premium to the inflation rate, and `portfolio/return` and `portfolio/withdrawal` use the risk-free and real rates.

## What the data holds

The `interest` table in `wrangle`'s Postgres, entities `Bank` (the risk-free rate), `Inflation` and `Net` (the real return of cash), each as the mean over 1, 5, 10, 20 and 40 years, from the Reserve Bank `f04hist` table (retail rates) and the `Rates` sheet.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_economy_rates_in` | FP64 | Unused, required so the request is still validated |
| Output | `finance_economy_rates_inflation_low_pct` | FP64 | Annual inflation rate, low scenario, percent per year. |
| Output | `finance_economy_rates_inflation_base_pct` | FP64 | Annual inflation rate, base scenario, percent per year. |
| Output | `finance_economy_rates_inflation_high_pct` | FP64 | Annual inflation rate, high scenario, percent per year. |
| Output | `finance_economy_rates_riskfree_low_pct` | FP64 | Annual risk-free (bank) rate, nominal, low scenario, percent per year. |
| Output | `finance_economy_rates_riskfree_base_pct` | FP64 | Annual risk-free (bank) rate, nominal, base scenario, percent per year. |
| Output | `finance_economy_rates_riskfree_high_pct` | FP64 | Annual risk-free (bank) rate, nominal, high scenario, percent per year. |
| Output | `finance_economy_rates_real_low_pct` | FP64 | Annual real return of cash, low scenario, percent per year. |
| Output | `finance_economy_rates_real_base_pct` | FP64 | Annual real return of cash, base scenario, percent per year. |
| Output | `finance_economy_rates_real_high_pct` | FP64 | Annual real return of cash, high scenario, percent per year. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `economy_rates_training` | The 5, 10, 20 and 40 year window means of the bank rate, inflation and the real return of cash, synthetic until the `interest` table is read |
| `golden` | `economy_rates_golden` | One valid request, then a request with the input missing, which must give a signature error |

## Acceptance

None. A `static` project carries no evaluation (R14); the gate is the golden replay, which reproduces the constants exactly, and the Fit cell asserts the identity.

## Approach

**Inflation.**

1. **Look at the windows.** Plot the 1, 5, 10, 20 and 40 year means over time. If the recent windows sit inside the Reserve Bank's 2 to 3 percent target while the 40 year mean is 3.24, the long mean is carrying the high inflation of the early period.
2. **Model it as mean reverting to an anchored target.** An AR(1) in the annual rate, pulled toward a target that is itself a shrinkage between the Reserve Bank's target and the long run mean. The pull strength is estimated from the quarterly history.
3. **Regimes.** A two state model (anchored and de-anchored) lets the high scenario be a regime with a stated chance, not a bigger variance. Terminology: this is a **regime switching** or **Markov switching** model, and the scenarios are the regime paths.
4. **Simulate to 2070** and take the **compound** rate of each path; low, base and high are percentiles.
5. **Ship** the three rates. `household/costs` consumes the base as its inflation component and adds its premium; `portfolio/return` uses it to turn a nominal into a real return.

**Risk-free and real.**

1. **Look at the term structure of the windows.** `Bank` at 5, 10, 20 and 40 years shows the regimes, and `Net` shows that the real return of cash has been far smaller and far less stable than the nominal one.
2. **Model the real rate, not the nominal.** The real cash rate is the steadier series, so model `Net` as mean reverting and add inflation from the step above to get the nominal. This keeps the two forecasts consistent by construction (Fisher relation).
3. **Simulate** the pair and take compound rates, low, base and high as percentiles.
4. **Ship** the nominal and the real rates.

Placeholder: low, base and high are the 40, 10 and 5 year `Bank` means ordered, until step 3.

Placeholder: low, base and high are the smallest, the mean and the largest of the window means of each series, with the identity asserted.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Index linked government bond yields | The market's real riskless rate, a better anchor than cash | Reserve Bank |
| Term deposit and offset rates actually available to you | The rate you really earn, net of the bank's margin | Your accounts, `Bank` workbook interest rows |
| Quarterly CPI, headline and trimmed mean | Underlying inflation without one-offs | Reserve Bank and ABS |
| Reserve Bank target and cash rate decisions | The anchor and the policy response | Reserve Bank |
| Inflation expectations: indexed bond breakevens, survey measures | A forward view that the history cannot give | Reserve Bank, Melbourne Institute |
| Wage price index | Wages drive services costs, and your income | ABS |

## Consumption

Target `served`. The planning sheet reads this model's numbers from `mlserver` through `wrangle`, the way it reads Yahoo Finance prices today, and that is **to be built later**:

- `wrangle`'s HTTP server (`server.py`) gains a feed that asks `mlserver` for the released `static` models and caches each answer with a TTL, so a recalculating sheet costs one call per model.
- The resource gets its own hostname through the `<MODULE>_HTTP_API_<RESOURCE>_CONTEXT` key in `wrangle`'s `.env_all`, which `nginx` turns into a vhost, and reaches Google through `cloudflare` behind the Access service token.
- The sheet calls it with an Apps Script custom function, as `src/build/resources/sheets/equity_price.js` does, for example `=WRANGLE_PLAN("finance_economy_rates", "base")`. `IMPORTDATA` cannot send the Access headers.
- The numbers are the model's three constant outputs (low, base and high), so the function picks one by name. Show the project hash with it so the sheet says which release a number came from.

Nothing here is built, and this model needs no change for it beyond staying `static` and `served`.

## To do

1. Add `query_postgres` and read the `Bank` and `Net` windows.
2. Compare the cash rate you earn (interest rows in the `Bank` workbook) with the published one.
3. Fit and write the golden samples.
