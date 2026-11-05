# inflation

The plan for the `finance_economy_inflation` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `economy` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/economy/inflation/notebook.ipynb` |
| **Registered Model** | `finance_economy_inflation` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2), target `served` |

**Status, 2026-11-05.** A placeholder. The notebook fits on a synthetic series, packages a `static` project, replays the golden and records it; the real series is not loaded yet and nothing is released.

## Intent

Give one annual inflation rate to 2070 for the economy, separate from `household/costs`. Costs are then inflation plus your own structural premium, so the two can be reasoned about, and checked, separately. It also deflates the return forecast into a real return without involving your spending.

## What the data holds

The `interest` table in `wrangle`'s Postgres, entity `Inflation`, from the Reserve Bank `g01hist` table and the `Rates` sheet: the mean rate over 1, 5, 10, 20 and 40 years (the 40 year mean is 3.24 percent). The windows are different regimes, which is the evidence the model is built on. Nothing else about inflation is held.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_economy_inflation_in` | FP64 | Unused, required by the spec so the request is still validated |
| Output | `finance_economy_inflation_annual_low_pct` | FP64 | Annual inflation rate, percent per year, low scenario. |
| Output | `finance_economy_inflation_annual_base_pct` | FP64 | Annual inflation rate, percent per year, base scenario. |
| Output | `finance_economy_inflation_annual_high_pct` | FP64 | Annual inflation rate, percent per year, high scenario. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell.

## Approach

1. **Look at the windows.** Plot the 1, 5, 10, 20 and 40 year means over time. If the recent windows sit inside the Reserve Bank's 2 to 3 percent target while the 40 year mean is 3.24, the long mean is carrying the high inflation of the early period.
2. **Model it as mean reverting to an anchored target.** An AR(1) in the annual rate, pulled toward a target that is itself a shrinkage between the Reserve Bank's target and the long run mean. The pull strength is estimated from the quarterly history.
3. **Regimes.** A two state model (anchored and de-anchored) lets the high scenario be a regime with a stated chance, not a bigger variance. Terminology: this is a **regime switching** or **Markov switching** model, and the scenarios are the regime paths.
4. **Simulate to 2070** and take the **compound** rate of each path; low, base and high are percentiles.
5. **Ship** the three rates. `household/costs` consumes the base as its inflation component and adds its premium; `portfolio/returns` uses it to turn a nominal into a real return.

Placeholder: low, base and high are the 2 percent floor, the 3.24 percent mean and a de-anchored rate, until step 4 replaces them.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Quarterly CPI, headline and trimmed mean | Underlying inflation without one-offs | Reserve Bank and ABS |
| Reserve Bank target and cash rate decisions | The anchor and the policy response | Reserve Bank |
| Inflation expectations: indexed bond breakevens, survey measures | A forward view that the history cannot give | Reserve Bank, Melbourne Institute |
| Wage price index | Wages drive services costs, and your income | ABS |

## Consumption

Target `served`. The planning sheet reads this model's numbers from `mlserver` through `wrangle`, the way it reads Yahoo Finance prices today, and that is **to be built later**:

- `wrangle`'s HTTP server (`server.py`) gains a feed that asks `mlserver` for the released `static` models and caches each answer with a TTL, so a recalculating sheet costs one call per model.
- The resource gets its own hostname through the `<MODULE>_HTTP_API_<RESOURCE>_CONTEXT` key in `wrangle`'s `.env_all`, which `nginx` turns into a vhost, and reaches Google through `cloudflare` behind the Access service token.
- The sheet calls it with an Apps Script custom function, as `src/build/resources/sheets/equity_price.js` does, for example `=WRANGLE_PLAN("finance_economy_inflation", "base")`. `IMPORTDATA` cannot send the Access headers.
- The numbers are the model's three constant outputs (low, base and high), so the function picks one by name. Show the project hash with it so the sheet says which release a number came from.

Nothing here is built, and this model needs no change for it beyond staying `static` and `served`.

## To do

1. Add `query_postgres` to `workbench.data` and read the `Inflation` windows.
2. Plot the windows and decide the anchor.
3. Fit step 2 and write the golden samples for the three scenarios and a missing input.
