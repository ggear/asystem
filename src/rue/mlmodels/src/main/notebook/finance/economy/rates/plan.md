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

Give one annual no risk (bank) rate to 2070 and the matching real return, so the floor of every return scenario and the discount rate of every spending annuity come from one place. `portfolio/returns` and `portfolio/spending` use it.

## What the data holds

The `interest` table in `wrangle`'s Postgres, entities `Bank` (the no risk rate), `Inflation` and `Net` (the real return of cash), each as the mean over 1, 5, 10, 20 and 40 years, from the Reserve Bank `f04hist` table (retail rates) and the `Rates` sheet.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_economy_rates_in` | FP64 | Unused, required by the spec so the request is still validated |
| Output | `finance_economy_rates_nominal_low_pct` | FP64 | Annual no risk rate, percent per year, low scenario. |
| Output | `finance_economy_rates_nominal_base_pct` | FP64 | Annual no risk rate, percent per year, base scenario. |
| Output | `finance_economy_rates_nominal_high_pct` | FP64 | Annual no risk rate, percent per year, high scenario. |
| Output | `finance_economy_rates_real_low_pct` | FP64 | Annual real return of cash, percent per year, low scenario. |
| Output | `finance_economy_rates_real_base_pct` | FP64 | Annual real return of cash, percent per year, base scenario. |
| Output | `finance_economy_rates_real_high_pct` | FP64 | Annual real return of cash, percent per year, high scenario. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell.

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
