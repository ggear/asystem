# mix

The plan for the `finance_portfolio_mix` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/mix/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_mix` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook recovers two assets (6 percent return and 15 volatility; 2 and 5) and a correlation of 0.2 from synthetic points; nothing is released.

## Intent

Give the two numbers every mix decision starts from, expected return and volatility, for any share held in risky assets. Placeholder: the risky and defensive assets and their correlation are recovered from synthetic points.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_mix_risky_share_pct` | FP64 | Share of the portfolio held in risky assets, 0 to 100 percent. |
| Output | `finance_portfolio_mix_return_pct` | FP64 | Expected annual return of the mix, percent. |
| Output | `finance_portfolio_mix_volatility_pct` | FP64 | Annualised volatility of the mix, percent. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_mix_training` | Ten risky shares with the return and volatility of the mix |
| `validation` | `portfolio_mix_validation` | Five further shares |
| `backtest` | `portfolio_mix_backtest` | Ten shares across the range, held back for acceptance |
| `golden` | `portfolio_mix_golden` | Shares from 0 to 100 percent, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Four gating checks, return and volatility on each of `validation` and `backtest`: the `rmse` must not exceed 0.05 percentage points.

## Approach

The investment mix decision project. It composes the other notebooks in this module into the numbers needed to choose the share held in risky assets, and it is the first thing to build for real once the inputs below exist.

How the module maps to the book (Haghani and White, `financial-decisions`):

| Book notebook | Here | Role in the decision |
|---|---|---|
| 0 rational choice | none | Theory, no model |
| 1 CRRA utility | `portfolio/utility` | Your risk aversion |
| 2 risk adjusted excess returns | `portfolio/excess` | Compares candidate mixes on one scale |
| 3 asymmetric payoffs | not built | Skew and crash risk, add if the mixes differ in tails |
| 4 riskless lifetime spending | `portfolio/spending` | The ceiling to beat |
| 5 lifetime spending with a risky asset | `portfolio/allocation` | The Merton share |
| 6 Monte Carlo | `portfolio/montecarlo` | Ruin probability and shortfall |
| none | `portfolio/mix` | Return and volatility of any blend, and the decision table |
| none | `household/costs`, `portfolio/returns` | What spending grows at and what the assets earn |
| none | `economy/inflation`, `economy/rates` | Inflation and the no risk rate that costs and returns are built on |
| none | `household/runrate`, `household/lumps`, `household/flexibility`, `household/income`, `household/networth` | What you spend, in what shape, what can be cut, what other income there is, and where you start |

**What you should have in front of you to decide a mix.** The notebook should end in one table, one row per candidate risky share, with these columns:

1. Expected compound return and volatility of the mix (this notebook).
2. Risk adjusted excess return at low, central and high risk aversion (`excess`).
3. The Merton share at the same three risk aversions, as a marker on the table (`allocation`).
4. Probability of ruin and expected shortfall to the horizon at your planned spending, using the base cost scenario (`montecarlo`).
5. The spending that holds ruin at 5 percent, so the decision reads as "this mix lets me spend X".
6. Worst peak to trough fall seen in the history (**maximum drawdown**), and the 5th percentile one year return, because what you can tolerate in a bad year is a constraint, not a preference to be averaged away.
7. Sensitivity: how the best share moves if the equity return is a point lower, if costs are in their high scenario, if inflation stays high. A share that is best only in the base case is a weak choice.

**What you should decide first, because the model cannot.** The spending you need and the part of it that is discretionary; the horizon and who it covers; your tolerance for a fall, in dollars; whether you will cut spending after a bad year; what other income there is (Age Pension, super, rent) and when; and whether you want to leave a bequest.

Decision method: choose the highest share that keeps ruin at or below your limit at the high cost scenario, then check it is not above the Merton share at your highest risk aversion. If the two disagree, the cause is usually spending, not asset choice, and the next step is `montecarlo` with a spending cut rule.

Placeholder in this notebook: the mix is a two asset blend; return is a line and variance a quadratic in the risky share.

## Data to get

Beyond what `wrangle` holds today (`equity` prices, `currency`, `interest`):

| Data | Why | Where from |
|---|---|---|
| Holdings and weights as a history | Weights are only in the Portfolio sheet, not Postgres | `wrangle` equity plugin, new table |
| Distributions and franking | Total return, not price | Fund registries |
| Return history for bonds, cash, property and gold as total returns | The defensive and diversifying side of the mix | `wrangle` interest table, fund data |
| Correlations by regime (calm, crisis) | One correlation understates diversification failure | Built from the history, including 2008 and 2020 |
| Spending history by category and the discretionary share | Whether you can cut | The costs sheet |
| Other income: Age Pension, super, rent, and their start dates | The income floor | Services Australia, super statements |
| Life tables | Survival, joint with Jane | ABS |
| Tax: marginal rates, franking, super tax, capital gains | After tax return | Your tax returns |
| Fees on each fund | Net return | Fund disclosures |
| Your risk aversion, elicited | `gamma` | The `portfolio/utility` questionnaire |
| Tolerance for a fall, in dollars | The drawdown constraint | A conversation, written down |
| Home equity and other assets, and whether they are in or out of the pool | What the mix has to carry | Your balance sheet |
| Forward capital market assumptions | Base for returns | Published assumptions |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
