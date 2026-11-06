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

Give the share of the portfolio to hold in risky assets that maximises utility, and the risk-adjusted excess return, at a given volatility, so the share follows the volatility you expect and portfolios of different risk compare on one number. Both are functions of the same two parameters, the excess return and the risk aversion, fitted once, so the share and the risk-adjusted return cannot disagree. The share is the Merton share, an upper bound, and the risk-adjusted return puts a 100 percent equity portfolio and a 60/40 one on one scale.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_allocation_volatility_pct` | FP64 | Annualised volatility of the risky assets, percent. |
| Output | `finance_portfolio_allocation_risky_pct` | FP64 | Share of the portfolio to hold in risky assets that maximises utility, 0 to 100 percent. |
| Output | `finance_portfolio_allocation_riskadjusted_pct` | FP64 | Excess return over cash less the charge for volatility, percent per year. |

`model.py` calls `set_model` and imports nothing beyond the base packages and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_allocation_training` | Ten volatilities with the share and the risk-adjusted return |
| `validation` | `portfolio_allocation_validation` | Five further |
| `backtest` | `portfolio_allocation_backtest` | Ten across the range, held back for acceptance |
| `golden` | `portfolio_allocation_golden` | Volatilities from 5 to 60 percent, then a request with the input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`model.md` 6.8). Four gating checks: the `rmse` of each output on `validation` and on `backtest` must not exceed 0.01.

## Approach

From `5-lifetime-spending-with-risky-asset`. The **Merton share** is the fraction of wealth to hold in the risky asset: `(mu - r) / (gamma * sigma^2)`, capped at 100 percent (no leverage). The notebook fits one coefficient, `(mu - r) / gamma`, and the plan notes that excess return and risk aversion are not separable from share data alone, so they are carried as separate named inputs in the later model.

Method: replace the fitted excess return by the one built from `portfolio/return` and `economy/rates`, and the fitted `gamma` by the one from `portfolio/utility`, and expose the share as a function of both, so you can read off how the answer moves. Report the share at low, central and high `gamma`. Treat the result as an upper bound, because it assumes constant `mu` and `sigma`, no income floor and no taxes.

**Risk-adjusted return.** From `2-approximating-risk-adjusted-excess-returns`. For a portfolio with expected return `mu`, cash rate `r` and volatility `sigma`, the value to a CRRA investor is close to `(mu - r) - gamma * sigma^2 / 2`, the **risk adjusted excess return**. It puts portfolios of different risk on one scale, so a 100 percent equity portfolio and a 60/40 one can be compared by the number that matters.

Method: take `mu`, `r` and `sigma` for each candidate portfolio from `portfolio/return` and `economy/rates`, and `gamma` from `portfolio/utility`. Report the number as a table over `gamma` low, central and high, since the ranking can flip. The notebook fits the same line to labelled points, as the placeholder does.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Excess return and volatility per asset class | The inputs of the formula | `portfolio/return` and `wrangle` |
| Leverage and borrowing limits | Whether the cap is 100 percent | Your own rule |
| Cash rate history | `r` | `wrangle` interest table |
| Volatility of each candidate portfolio | `sigma` | Built from `portfolio/return` history |

## Personal data

Real personal financial data MUST NOT be committed (`wrangle`'s rule, applied to `mlmodels`; see its `CLAUDE.md`). The `data/` captures of this workspace are git-ignored in the root `.gitignore`; the real inputs are your holdings, spending and elicited preferences, and none of them is recorded in a plan, a notebook or a test. What is committed here is synthetic, and the notebook rebuilds the placeholder when the files are absent. Check `git status` before staging.

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
