# montecarlo

The plan for the `finance_portfolio_montecarlo` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/montecarlo/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_montecarlo` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook simulates 2000 paths with a fixed seed, fits a logistic curve to the ruin probability and replays; nothing is released.

## Intent

Turn a spending rate into a ruin probability under risky returns, the number a spending decision is made on. Placeholder: a fixed seed simulation labels the data and a logistic curve is fitted to it.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_montecarlo_spending_rate_pct` | FP64 | Initial annual spending as a percent of wealth, held constant in real terms. |
| Output | `finance_portfolio_montecarlo_ruin_pct` | FP64 | Percent of simulated paths that run out of money within 30 years. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_montecarlo_training` | Ten spending rates with the simulated ruin percent |
| `validation` | `portfolio_montecarlo_validation` | Five further rates |
| `backtest` | `portfolio_montecarlo_backtest` | Ten rates across the range, held back for acceptance |
| `golden` | `portfolio_montecarlo_golden` | Rates from zero to 12 percent, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_portfolio_montecarlo_ruin_pct`: the `rmse` of the fitted curve against the simulation on `validation` and `backtest` must not exceed 8 percentage points. The placeholder measures about 2.

## Approach

From `6-monte-carlo`. **Ruin** is wealth reaching zero before the horizon. The placeholder draws normal real returns (4 percent mean, 12 percent volatility) and spends a fixed real amount; the same draws serve every rate, so the curve is smooth (**common random numbers**).

Method, to replace the placeholder:

1. Draw returns by **stationary block bootstrap** from the `portfolio/returns` history, re-centred on its forward base, so fat tails and runs of bad years are in the data and not assumed away.
2. Draw inflation from `household/costs` jointly with returns, because a bad return year and a high cost year arrive together.
3. Use survival from `portfolio/spending` instead of a fixed 30 years.
4. Report the ruin probability, the **expected shortfall** (average depth of ruin) and the 5th percentile terminal wealth, not ruin alone, which treats running out in year 29 like year 5.
5. Try a flexible rule (cut spending by a fixed fraction after a bad year, the guardrail rule), because the largest improvement in ruin comes from being able to cut, not from any asset choice.

The served model is the cheap summary (the curve); the simulation stays in the notebook as evidence.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Joint monthly returns and inflation history | Block bootstrap | `wrangle`, ABS |
| Survival curve | Horizon | ABS life tables |
| Your minimum and discretionary spending | Whether a spending cut is possible | The costs sheet by category |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
