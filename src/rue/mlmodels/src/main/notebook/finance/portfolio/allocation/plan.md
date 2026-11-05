# allocation

The plan for the `finance_portfolio_allocation` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/allocation/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_allocation` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook recovers a coefficient of 1.5 from synthetic shares; nothing is released.

## Intent

Give the Merton share, the excess return over the risk aversion times the variance, so the risky share follows the volatility you expect. Placeholder: the single coefficient is recovered from synthetic points.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_allocation_volatility_pct` | FP64 | Annualised volatility of the risky assets, percent. |
| Output | `finance_portfolio_allocation_risky_pct` | FP64 | Share of the portfolio held in risky assets, 0 to 100 percent. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_allocation_training` | Ten volatilities with the share, none capped |
| `validation` | `portfolio_allocation_validation` | Five further |
| `backtest` | `portfolio_allocation_backtest` | Ten across the range, five of them at the cap, held back for acceptance |
| `golden` | `portfolio_allocation_golden` | Volatilities from 5 to 60 percent, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_portfolio_allocation_risky_pct`: the `rmse` on `validation` and `backtest` must not exceed 0.01.

## Approach

From `5-lifetime-spending-with-risky-asset`. The **Merton share** is the fraction of wealth to hold in the risky asset: `(mu - r) / (gamma * sigma^2)`, capped at 100 percent (no leverage). The notebook fits one coefficient, `(mu - r) / gamma`, and the plan notes that excess return and risk aversion are not separable from share data alone, so they are carried as separate named inputs in the later model.

Method: replace the single coefficient by `excess` from `portfolio/excess` and `gamma` from `portfolio/utility`, and expose the share as a function of both, so you can read off how the answer moves. Report the share at low, central and high `gamma`. Treat the result as an upper bound, because it assumes constant `mu` and `sigma`, no income floor and no taxes.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Excess return and volatility per asset class | The inputs of the formula | `forecast/returns` and `wrangle` |
| Leverage and borrowing limits | Whether the cap is 100 percent | Your own rule |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
