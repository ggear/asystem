# spending

The plan for the `finance_portfolio_spending` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/spending/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_spending` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook recovers a 2 percent real return to age 100 from synthetic rates; nothing is released.

## Intent

Give the spending rate a riskless real return supports to a planning horizon, the ceiling any risky mix has to beat. Placeholder: the real return is recovered from synthetic points.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_spending_age_years` | FP64 | Age in years. |
| Output | `finance_portfolio_spending_rate_pct` | FP64 | Annual spending as a percent of wealth that a riskless real return sustains to the planning horizon. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_spending_training` | Ten ages with the sustainable rate |
| `validation` | `portfolio_spending_validation` | Five further ages |
| `backtest` | `portfolio_spending_backtest` | Ten ages across the range, held back for acceptance |
| `golden` | `portfolio_spending_golden` | Ages 30 to 120, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_portfolio_spending_rate_pct`: the `rmse` on `validation` and `backtest` must not exceed 0.01.

## Approach

From `4-riskless-lifetime-spending`. With a riskless real return `r` and a horizon of `n` years the level real spending that exactly exhausts wealth is the annuity rate `r / (1 - (1 + r)^-n)`. It is the ceiling a risky mix has to beat to be worth the risk.

Method: replace the fixed horizon with the survival curve (`findec.survival` in the book's code, from Australian life tables), so the horizon is the chance of being alive each year, not a fixed age, and use a joint survival for you and Jane. Take `r` from the index linked bond yield. Add the Age Pension and superannuation preservation as an income floor, which lowers the rate you need from wealth.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Australian life tables, by sex and age | Survival instead of a fixed horizon | ABS |
| Index linked bond yields | The riskless real return | RBA, `wrangle` interest table |
| Age Pension rules and means tests | Income that does not come from wealth | Services Australia |
| Superannuation balances, preservation age, withdrawal rules | When and how the money can be spent | Super fund statements |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
