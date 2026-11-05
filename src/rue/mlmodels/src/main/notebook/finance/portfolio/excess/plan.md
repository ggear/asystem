# excess

The plan for the `finance_portfolio_excess` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/excess/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_excess` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2), target `local` |
| **Target** | `local`: it never leaves the notebook and `mlserver` cannot pull it. Promote it by changing the target to `served` when something needs to call it |

**Status.** Placeholder. The notebook recovers a 4 percent excess return and a risk aversion of 3 from synthetic points; nothing is released.

## Intent

Show what is left of a portfolio's excess return once its volatility is charged for, so portfolios of different risk compare on one number. Placeholder: the excess return and risk aversion are recovered from synthetic points.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_excess_volatility_pct` | FP64 | Annualised volatility of the portfolio, percent. |
| Output | `finance_portfolio_excess_risk_adjusted_pct` | FP64 | Excess return over cash less the charge for volatility, percent per year. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS`. Promoting it to `served` needs no new package in `mlserver` either.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_excess_training` | Ten volatilities with the risk adjusted excess return |
| `validation` | `portfolio_excess_validation` | Five further |
| `backtest` | `portfolio_excess_backtest` | Ten across the range, held back for acceptance |
| `golden` | `portfolio_excess_golden` | Volatilities from zero to 30 percent, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_portfolio_excess_risk_adjusted_pct`: the `rmse` on `validation` and `backtest` must not exceed 0.01.

## Approach

From `2-approximating-risk-adjusted-excess-returns`. For a portfolio with expected return `mu`, cash rate `r` and volatility `sigma`, the value to a CRRA investor is close to `(mu - r) - gamma * sigma^2 / 2`, the **risk adjusted excess return**. It puts portfolios of different risk on one scale, so a 100 percent equity portfolio and a 60/40 one can be compared by the number that matters.

Method: take `mu`, `r` and `sigma` for each candidate portfolio from `portfolio/returns` and the `interest` table, and `gamma` from `portfolio/utility`. Report the number as a table over `gamma` low, central and high, since the ranking can flip. The notebook fits the same line to labelled points, as the placeholder does.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Cash rate history | `r` | `wrangle` interest table |
| Volatility of each candidate portfolio | `sigma` | Built from `portfolio/returns` history |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
