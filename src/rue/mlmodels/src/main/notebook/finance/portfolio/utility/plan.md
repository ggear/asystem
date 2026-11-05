# utility

The plan for the `finance_portfolio_utility` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/utility/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_utility` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2), target `local` |
| **Target** | `local`: it never leaves the notebook and `mlserver` cannot pull it. Promote it by changing the target to `served` when something needs to call it |

**Status.** Placeholder. The notebook recovers a risk aversion of 3 from synthetic utilities; the real input is your own choices and nothing is released.

## Intent

Turn a wealth multiple into utility so a portfolio can be ranked by what it is worth to you and not by its average. Placeholder: the risk aversion is recovered from synthetic utilities.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_utility_wealth` | FP64 | Wealth as a multiple of today's wealth. |
| Output | `finance_portfolio_utility_value` | FP64 | Constant relative risk aversion utility of the wealth multiple. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS`. Promoting it to `served` needs no new package in `mlserver` either.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_utility_training` | Ten wealth multiples with their utility |
| `validation` | `portfolio_utility_validation` | Five larger multiples |
| `backtest` | `portfolio_utility_backtest` | Ten multiples across the range, held back for acceptance |
| `golden` | `portfolio_utility_golden` | Wealth multiples from half to ten, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_portfolio_utility_value`: the `rmse` on `validation` and `backtest` must not exceed 0.001.

## Approach

From Haghani and White, *The Missing Billionaires*, `1-crra-utility`. Utility of wealth `w` with relative risk aversion `gamma` is `w^(1 - gamma) / (1 - gamma)`, or `log w` at `gamma = 1`. Everything else in `portfolio/` is a consequence of the one number `gamma`.

Terminology: **constant relative risk aversion** (CRRA) means you hold the same share in risky assets whatever your wealth. **Certainty equivalent** is the sure wealth you would swap for a gamble, and is how `gamma` is measured.

Method: ask the questions the book asks, a series of 50/50 gambles on a fraction of your wealth with the sure amount you would accept, and fit `gamma` to the certainty equivalents. Do it twice, a year apart and with Jane, because a `gamma` that moves with the day is noise. Report the range, not a point: the later notebooks take a low, central and high `gamma`.

Placeholder: the fit recovers 3 from synthetic utilities of wealth.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Your certainty equivalents for a set of gambles, and Jane's | `gamma` is a preference, not a market number | A short questionnaire kept as a `training` file |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
