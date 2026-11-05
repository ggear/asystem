# costs

The plan for the `finance_household_costs` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/costs/notebook.ipynb` |
| **Registered Model** | `finance_household_costs` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook fits, accepts, packages and replays on synthetic series around the two long run means; no real data is loaded yet and nothing is released.

## Intent

Give one annual cost growth rate per scenario to inflate spending to 2070. Placeholder: the base is the mean observed cost growth and the low is the mean inflation, with the high mirroring the structural premium of cost growth over inflation.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_household_costs_scenario` | FP64 | Scenario, 0 low, 1 base, 2 high. |
| Output | `finance_household_costs_growth_pct` | FP64 | Annual growth rate of costs for the scenario, percent per year. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `household_costs_training` | Ten years of annual inflation and cost growth, synthetic around 3.24 and 4.83 percent. To be replaced by the two sheets below |
| `validation` | `household_costs_validation` | Five further years of observed cost growth against the base scenario |
| `backtest` | `household_costs_backtest` | Ten more years, held back for acceptance |
| `golden` | `household_costs_golden` | Scenarios 0, 1, 2, rounding cases and out of range ones, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_household_costs_growth_pct`: the `rmse` of the base scenario against observed growth on `validation` and `backtest` must not exceed 1.0 percentage point. The placeholder noise is about 0.3 to 0.5.

## Approach

Goal: one annual growth rate for the household's costs to 2070, as a low, base and high scenario, usable directly in the lifetime model (`portfolio/montecarlo`, `portfolio/mix`).

Sources named so far, both Google Sheets, to be downloaded by `wrangle` and read through `workbench.data`:

| Source | Series | Figure to anchor to |
|---|---|---|
| Inflation sheet (gid 361906297) | Annual inflation | 40 year mean 3.24 percent |
| Costs sheet (gid 41251010) | Household costs, growth Y/Y, all months | Mean 4.83 percent |

The `Inflation` series is already in Postgres: the `interest` table has entity `Inflation` with the mean over 1, 5, 10, 20 and 40 years, from the same Reserve Bank sheet as the 3.24 percent figure (the 40 year mean). The shorter windows are the evidence for the mean reversion below: if the 5 and 10 year means sit near the 2 to 3 percent target while the 40 year mean is 3.24, the long mean is carrying the early high inflation and the base should lean on the target. `portfolio/returns` uses the same table for the no risk rate (`Bank`) and the real return of cash (`Net`), so the two numbers share one source and one set of windows.

Two cautions before trusting 4.83 percent. The `Bank` workbook's statement history begins on 2021-05-01, so there are fewer than five year over year growth points, against a 40 year inflation window: compare 5 years with 5 years (the `Inflation` 5 year mean), not with the 40 year mean. And a growth rate over all spending moves when one large item falls in or out of a year; `household/runrate` separates the normal spend from the one-offs and `household/lumps` models the one-offs, so this notebook can forecast the growth of normal spending and leave the lumps to their own model. Inflation itself is `economy/inflation`, so the cost growth here is that rate plus the household's premium.

Terminology to keep straight, since it decides the number:

- **Nominal against real.** The portfolio returns are nominal, so costs are forecast nominal and the real rate is the difference (Fisher relation, `(1 + nominal) / (1 + inflation) - 1`), not the subtraction.
- **Headline CPI against a household cost index.** CPI weights an average household. Your own costs grew 1.6 points a year faster than CPI (4.83 against 3.24). That gap is the **structural premium** (relative price change, Baumol cost disease in services, lifestyle drift), and it is forecast separately from inflation.
- **Compound, not arithmetic.** The single number is the **compound annual growth rate** of the simulated cost index to 2070, not the mean of yearly rates, which overstates it.
- **Scenario against distribution.** A scenario is a named set of assumptions about the structural drivers. A projection is a distribution. Report both: the scenarios are anchors you can reason about, the percentile band says how wide the doubt is.

Method, in order of cost and value:

1. **Decompose.** Cost growth = expected inflation + structural premium + noise. Fit each on the sheets.
2. **Mean revert, do not extrapolate.** The 40 year mean contains the high inflation of the early period. Model inflation as a mean reverting process (an AR(1), the discrete Ornstein-Uhlenbeck) pulled toward the Reserve Bank's 2 to 3 percent target, with the pull strength estimated and the anchor set by shrinking between the long run mean and the target. The premium is a second mean reverting spread.
3. **Simulate to 2070.** Draw 10,000 paths of the pair (stationary block bootstrap of the residuals keeps the serial dependence), compound each, and take the compound rate of each path. The base is the median path, the low and high the 25th and 75th percentiles (or 10th and 90th if you want a harder test).
4. **Condition the scenarios on drivers** that the data cannot see: ageing and health and aged-care cost growth, the energy transition, insurance and housing costs, de-urbanisation, and the chance of cost saving from downsizing. Each driver moves the premium or the anchor by a stated amount, so a scenario is traceable to its cause.
5. **Ship** the three compound rates (this notebook) and keep the simulation in the notebook as evidence, as `portfolio/montecarlo` does.

Placeholder in this notebook: low is the inflation mean, base the cost growth mean, high mirrors the premium. It is a lookup of three numbers and will be replaced by the output of step 3.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Cost growth by category (housing, food, health, insurance, energy, travel, aged care) | The premium differs by category and the mix changes with age | The costs sheet already has the lines, `wrangle` needs a category cut |
| ABS Selected Living Cost Indexes, retiree and age pensioner households | A published household cost index to check your premium against | ABS |
| Reserve Bank target, forecasts and inflation expectations; indexed bond breakevens | The anchor for the mean reversion, and a market view | RBA, `wrangle` interest table |
| Treasury Intergenerational Report health and aged-care cost projections | Evidence for the ageing driver | Treasury |
| Energy and insurance price outlooks | Evidence for those drivers | AEMO Integrated System Plan, insurer indices |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
4. Add `household/income` beside this notebook for Age Pension, superannuation and rent, the income floor that `portfolio/spending` and `portfolio/mix` need.
