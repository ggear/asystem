# costs

The plan for the `finance_household_costs` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/costs/notebook.ipynb` |
| **Registered Model** | `finance_household_costs` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2), target `served` |
| **Target** | `served` by `mlserver`. |

**Status, 2026-11-05.** A placeholder. The notebook fits on synthetic series, packages a `static` project, replays the golden and records it; the real series are not loaded yet and nothing is released.

## Intent

Give the baseline annual cost of running the household, split into the part that cannot be cut and the discretionary share, the expected and one-in-twenty annual cost of the irregular expenses, and the annual rate that costs grow at to 2070 under a low, base and high scenario, so spending can be projected as the cost grown at the rate and a bad year provisioned for. Five measures of one thing: the first three are how much a normal year costs and how much of it could be cut, the fourth is what the lumps add, and the growth is how fast it moves. They come from one classification of the transactions into regular and irregular, so they reconcile: the normal cost, the essential floor and the discretionary share are the regular rows, and the irregular expenses are the rest. The growth is measured on the regular rows so that one large item cannot move it, and inflation itself is `economy/rates`, so the growth here is that rate plus the household's premium.

## What the data holds

The `Bank` workbook that `wrangle`'s `bank` plugin writes (tabs `Accounts`, `Classifier`, `Balances`, `Transactions_<year>` and the `Summary` and `Logs` outputs), on Drive under `Wrangle/Bank/release/data`. Its transactions begin on 2021-05-01, when the statement history begins, each with a `Category` that the `Classifier` tab maps to a bucket. `bank` writes nothing to Postgres yet, so the first change for every household project is a `bank` table in `wrangle`'s schema, or a loader that reads the year files. The history is about 5 years, so the first year over year growth point is 2022-05 and there are fewer than 5 of them: that growth figure is a short sample, compared above with the 40 year inflation window. Compare like with like (the 5 year inflation mean).

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_household_costs_in` | FP64 | Unused, required so the request is still validated |
| Output | `finance_household_costs_normal_annual_dollars` | FP64 | Normal annual cost of running the household, with the irregular expenses taken out, dollars. |
| Output | `finance_household_costs_essential_dollars` | FP64 | Annual cost that cannot be cut, the essential and committed classes, dollars. |
| Output | `finance_household_costs_discretionary_pct` | FP64 | Share of the normal annual cost that is discretionary, percent. |
| Output | `finance_household_costs_irregular_expected_dollars` | FP64 | Expected annual cost of irregular expenses, dollars. |
| Output | `finance_household_costs_irregular_p95_dollars` | FP64 | Annual cost of irregular expenses that is exceeded one year in twenty, dollars. |
| Output | `finance_household_costs_growth_low_pct` | FP64 | Annual growth rate of costs, low scenario, percent per year. |
| Output | `finance_household_costs_growth_base_pct` | FP64 | Annual growth rate of costs, base scenario, percent per year. |
| Output | `finance_household_costs_growth_high_pct` | FP64 | Annual growth rate of costs, high scenario, percent per year. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell. Units tell the measures apart: dollars are a level, percent is a share or a growth.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `household_costs_training` | Seventy two months of synthetic spending by category and class (essential, committed, discretionary, irregular), until the `bank` table exists |
| `training` | `household_costs_growth_training` | Ten years of synthetic inflation and cost growth, until the real series are loaded |
| `golden` | `household_costs_golden` | One valid request, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before the real data can be loaded.

## Acceptance

None. A `static` project carries no evaluation (R14); the gate is the golden replay, which reproduces the constants exactly.

## Approach

**Normal annual cost.**

1. **Explore.** Monthly spend by category as a table and a heat map, the transfers, interest and tax categories left out (`Bank Transfer`, `Credit Payment` and the `Excluded` bucket are movements of money and not spending).
2. **Find the one-offs.** Flag a category-month more than a robust threshold above the category's median (median absolute deviation), and every row over a stated amount. Look at them by hand, then write the rule into the `Classifier` or here. The one-offs are the irregular expenses modelled below, from the same rows.
3. **Compute the run rate.** Trailing twelve months of regular spend by category, summed. This is the normal annual cost, and the series the growth below is measured on, so a single large item cannot move the growth rate.

**Classification and the floor.**

1. **Classify the categories** by how fixed they are, using a table kept in the notebook: **essential** (cannot stop without harm), **committed** (contracts and fees you could end but not quickly), **discretionary** (can stop at once) and **irregular**.
2. **Check the classification against behaviour.** A category that fell sharply in a past month without harm was discretionary. The data shows which categories ever moved, which is better than opinion. The robust rule of the first step must find exactly the months with an irregular row, so the rule and the classes agree.
3. **Measure the cut.** The essential floor and the discretionary share of the latest twelve regular months, and the largest fall in a twelve month sum seen in the history (the demonstrated flexibility). `portfolio/profile` uses the floor as a guardrail rule.

**Irregular expenses.**

1. **Explore** the distribution of amounts per category: how many a year, how large, how skewed. A heavy tailed amount is a **lognormal** or a **Pareto** tail; a count a year is a **Poisson** process.
2. **Fit a compound Poisson** per category (a rate of events a year and an amount distribution), the standard model for lumpy costs, which can be simulated directly in `portfolio/profile`. Until there are enough years the expected value and the empirical 95th percentile of the annual totals stand in.
3. **Known schedules** (a car at an age, a roof at a life) are deterministic items with a date range, kept apart from the random ones.

**Growth.**

Goal: one annual growth rate for the household's costs to 2070, as a low, base and high scenario, applied to the normal annual cost above and used in the lifetime model (`portfolio/profile`, `portfolio/profile`).

Sources named so far, both Google Sheets, to be downloaded by `wrangle` and read through `workbench.data`:

| Source | Series | Figure to anchor to |
|---|---|---|
| Inflation sheet | Annual inflation | 40 year mean 3.24 percent |
| Costs sheet | Household costs, growth Y/Y, all months | The mean in the sheet, a personal figure not recorded here |

The `Inflation` series is already in Postgres: the `interest` table has entity `Inflation` with the mean over 1, 5, 10, 20 and 40 years, from the same Reserve Bank sheet as the 3.24 percent figure (the 40 year mean). The shorter windows are the evidence for the mean reversion below: if the 5 and 10 year means sit near the 2 to 3 percent target while the 40 year mean is 3.24, the long mean is carrying the early high inflation and the base should lean on the target. `portfolio/return` uses the same table for the risk-free rate (`Bank`) and the real return of cash (`Net`), so the two numbers share one source and one set of windows.

Two cautions before trusting the sheet's growth figure. The `Bank` workbook's statement history begins on 2021-05-01, so there are fewer than five year over year growth points, against a 40 year inflation window: compare 5 years with 5 years (the `Inflation` 5 year mean), not with the 40 year mean. And a growth rate over all spending moves when one large item falls in or out of a year; `household/costs` separates the normal spend from the one-offs and `household/costs` models the one-offs, so this notebook can forecast the growth of normal spending and leave the lumps to their own model. Inflation itself is `economy/rates`, so the cost growth here is that rate plus the household's premium.

Terminology to keep straight, since it decides the number:

- **Nominal against real.** The portfolio returns are nominal, so costs are forecast nominal and the real rate is the difference (Fisher relation, `(1 + nominal) / (1 + inflation) - 1`), not the subtraction.
- **Headline CPI against a household cost index.** CPI weights an average household. Your own costs may grow faster or slower than CPI. That gap is the **structural premium** (relative price change, Baumol cost disease in services, lifestyle drift), and it is forecast separately from inflation.
- **Compound, not arithmetic.** The single number is the **compound annual growth rate** of the simulated cost index to 2070, not the mean of yearly rates, which overstates it.
- **Scenario against distribution.** A scenario is a named set of assumptions about the structural drivers. A projection is a distribution. Report both: the scenarios are anchors you can reason about, the percentile band says how wide the doubt is.

Method, in order of cost and value:

1. **Decompose.** Cost growth = expected inflation + structural premium + noise. Fit each on the sheets.
2. **Mean revert, do not extrapolate.** The 40 year mean contains the high inflation of the early period. Model inflation as a mean reverting process (an AR(1), the discrete Ornstein-Uhlenbeck) pulled toward the Reserve Bank's 2 to 3 percent target, with the pull strength estimated and the anchor set by shrinking between the long run mean and the target. The premium is a second mean reverting spread.
3. **Simulate to 2070.** Draw 10,000 paths of the pair (stationary block bootstrap of the residuals keeps the serial dependence), compound each, and take the compound rate of each path. The base is the median path, the low and high the 25th and 75th percentiles (or 10th and 90th if you want a harder test).
4. **Condition the scenarios on drivers** that the data cannot see: ageing and health and aged-care cost growth, the energy transition, insurance and housing costs, de-urbanisation, and the chance of cost saving from downsizing. Each driver moves the premium or the anchor by a stated amount, so a scenario is traceable to its cause.
5. **Ship** the three compound rates (this notebook) and keep the simulation in the notebook as evidence, as `portfolio/profile` does.

Placeholder in this notebook: low is the inflation mean, base the cost growth mean, high mirrors the premium. It is a lookup of three numbers and will be replaced by the output of step 3.

## Data to get

| Data | Why | Where from |
|---|---|---|
| A clean transfer flag, so movements between your own accounts never count | A transfer counted as spending doubles it | `Classifier` bucket `Excluded`, check it covers the transfers |
| Vetted flag on every closed month | Only vetted months are totalled | `Transactions` tab, `Vetted` column |
| Longer history | More than 5 years for growth | Older statements, if they exist (`Wrangle/Bank/archive`) |
| Cost growth by category (housing, food, health, insurance, energy, travel, aged care) | The premium differs by category and the mix changes with age | The costs sheet already has the lines, `wrangle` needs a category cut |
| ABS Selected Living Cost Indexes, retiree and age pensioner households | A published household cost index to check your premium against | ABS |
| Reserve Bank target, forecasts and inflation expectations; indexed bond breakevens | The anchor for the mean reversion, and a market view | RBA, `wrangle` interest table |
| Treasury Intergenerational Report health and aged-care cost projections | Evidence for the ageing driver | Treasury |
| Energy and insurance price outlooks | Evidence for those drivers | AEMO Integrated System Plan, insurer indices |
| Which spending is for the children and for how long | Child care and school end on a known date, which is a timing and not a cut | A conversation, written into the notebook |
| Contract terms (insurance, loan, subscriptions) | What is committed and until when | Statements |
| Ages and replacement cycles of the house, cars and appliances | The deterministic schedule | A list in the notebook |
| Insurance quotes and rates notices | Known annual lumps | Statements |

## Consumption

Target `served`. The planning sheet reads this model's numbers from `mlserver` through `wrangle`, the way it reads Yahoo Finance prices today, and that is **to be built later**:

- `wrangle`'s HTTP server (`server.py`) gains a feed that asks `mlserver` for the released `static` models and caches each answer with a TTL, so a recalculating sheet costs one call per model.
- The resource gets its own hostname through the `<MODULE>_HTTP_API_<RESOURCE>_CONTEXT` key in `wrangle`'s `.env_all`, which `nginx` turns into a vhost, and reaches Google through `cloudflare` behind the Access service token.
- The sheet calls it with an Apps Script custom function, as `src/build/resources/sheets/equity_price.js` does, for example `=WRANGLE_PLAN("finance_household_costs", "growth_base")`. `IMPORTDATA` cannot send the Access headers.
- The numbers are the model's constant outputs (the normal annual cost and the low, base and high growth), so the function picks one by name. Show the project hash with it so the sheet says which release a number came from.

Nothing here is built, and this model needs no change for it beyond staying `static` and `served`.

## Personal data

Real personal financial data MUST NOT be committed (`wrangle`'s rule, applied to `mlmodels`; see its `CLAUDE.md`). The `data/` captures and the `project/` of this workspace are git-ignored in the root `.gitignore` (`metadata.json` holds hashes and release state, no values, and stays committed), because the constants are derived from real spending and balances. What is committed here is synthetic, and the notebook rebuilds the placeholder when the files are absent. Check `git status` before staging.

## To do

1. Add a `bank` table to `wrangle`'s schema, or a loader for the year files, and `query_postgres` to `workbench.data`.
2. Do the explore and one-off steps of the normal annual cost, write the category classification table, and decide the threshold.
3. Replace the placeholder growth fit with the method in the approach, measured on the normalised series, keeping the signature.
4. Fix the limits against real data, then register and review before any release.
5. Add `household/income` beside this notebook for Age Pension, superannuation and rent, the income floor that `portfolio/withdrawal` and `portfolio/profile` need.
