# profile

The plan for the `finance_portfolio_profile` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/profile/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_profile` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook recovers two assets (6 percent return and 15 volatility; 2 and 5) and a correlation of 0.2 from synthetic points; nothing is released.

## Intent

Give, for any share held in risky assets and any withdrawal rate, the expected return and volatility of the mix and the probability that the portfolio runs out of money within 30 years, so a mix and a withdrawal can be compared on risk, return and the chance of a shortfall. The shortfall simulation uses the return and volatility that the same model gives for the share, so they cannot disagree.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_profile_risky_share_pct` | FP64 | Share of the portfolio held in risky assets, 0 to 100 percent. |
| Input | `finance_portfolio_profile_withdrawal_rate_pct` | FP64 | Initial annual withdrawal as a percent of wealth, constant in real terms. |
| Output | `finance_portfolio_profile_return_pct` | FP64 | Expected real return of the mix, percent per year. |
| Output | `finance_portfolio_profile_volatility_pct` | FP64 | Annualised volatility of the mix, percent. |
| Output | `finance_portfolio_profile_shortfall_probability_pct` | FP64 | Probability, in percent, that the portfolio runs out of money within 30 years. |

`model.py` calls `set_model` and imports nothing beyond the base packages and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_profile_training` | Thirty combinations of share and withdrawal rate with the return, volatility and simulated shortfall probability |
| `validation` | `portfolio_profile_validation` | Twenty further combinations |
| `backtest` | `portfolio_profile_backtest` | Twenty across the range, held back for acceptance |
| `golden` | `portfolio_profile_golden` | Shares from 0 to 100 percent with withdrawal rates from 2 to 6, then a request with an input missing, which must give a signature error |

## Acceptance

The notebook owns the limits (`model.md` 6.8). Six gating checks, the `rmse` of each output on `validation` and on `backtest`: the return and the volatility must not exceed 0.05 percentage points, and the shortfall probability 10 points, which is wide because the curve summarises a simulation (the placeholder measures about 5 to 6).

## Approach

The investment mix decision project. It composes the other notebooks in this module into the numbers needed to choose the share held in risky assets, and it is the first thing to build for real once the inputs below exist.

How the module maps to the book (Haghani and White, `financial-decisions`):

| Book notebook | Here | Role in the decision |
|---|---|---|
| 0 rational choice | none | Theory, no model |
| 1 CRRA utility | `portfolio/utility` | Your risk aversion |
| 2 risk adjusted excess returns | `portfolio/allocation` | Compares candidate mixes on one scale |
| 3 asymmetric payoffs | not built | Skew and crash risk, add if the mixes differ in tails |
| 4 riskless lifetime spending | `portfolio/withdrawal` | The ceiling to beat |
| 5 lifetime spending with a risky asset | `portfolio/allocation` | The Merton share |
| 6 Monte Carlo | `portfolio/profile` | Ruin probability and shortfall |
| none | `portfolio/profile` | Return and volatility of any blend, and the decision table |
| none | `household/costs`, `portfolio/return` | What a normal year costs, how fast that grows and what the assets earn |
| none | `economy/rates` | Inflation and the risk-free rate that costs and returns are built on |
| none | `household/costs`, `household/income`, `household/networth` | What you spend, in what shape, what can be cut, what other income there is, and where you start |

**What you should have in front of you to decide a mix.** The notebook should end in one table, one row per candidate risky share, with these columns:

1. Expected compound return and volatility of the mix (this notebook).
2. Risk adjusted excess return at low, central and high risk aversion (`portfolio/allocation`).
3. The Merton share at the same three risk aversions, as a marker on the table (`portfolio/allocation`).
4. Probability of ruin and expected shortfall to the horizon at your planned spending, using the base cost scenario (this notebook).
5. The spending that holds ruin at 5 percent, so the decision reads as "this mix lets me spend X".
6. Worst peak to trough fall seen in the history (**maximum drawdown**), and the 5th percentile one year return, because what you can tolerate in a bad year is a constraint, not a preference to be averaged away.
7. Sensitivity: how the best share moves if the equity return is a point lower, if costs are in their high scenario, if inflation stays high. A share that is best only in the base case is a weak choice.

**What you should decide first, because the model cannot.** The spending you need and the part of it that is discretionary; the horizon and who it covers; your tolerance for a fall, in dollars; whether you will cut spending after a bad year; what other income there is (Age Pension, super, rent) and when; and whether you want to leave a bequest.

Decision method: choose the highest share that keeps ruin at or below your limit at the high cost scenario, then check it is not above the Merton share at your highest risk aversion. If the two disagree, the cause is usually spending, not asset choice, and the next step is the shortfall simulation with a spending cut rule.

Placeholder in this notebook: the mix is a two asset blend; return is a line and variance a quadratic in the risky share.

**Shortfall.** From `6-monte-carlo`. A **shortfall** (ruin) is wealth reaching zero before the horizon. The placeholder draws normal real returns (4 percent mean, 12 percent volatility) and spends a fixed real amount; the same draws serve every rate, so the curve is smooth (**common random numbers**).

Method, to replace the placeholder:

1. Draw returns by **stationary block bootstrap** from the `portfolio/return` history, re-centred on its forward base, so fat tails and runs of bad years are in the data and not assumed away.
2. Draw inflation from `household/costs` jointly with returns, because a bad return year and a high cost year arrive together.
3. Use survival from `portfolio/withdrawal` instead of a fixed 30 years.
4. Report the shortfall probability (ruin), the **expected shortfall** (average depth of ruin) and the 5th percentile terminal wealth, not ruin alone, which treats running out in year 29 like year 5.
5. Try a flexible rule (cut spending by a fixed fraction after a bad year, the guardrail rule), because the largest improvement in ruin comes from being able to cut, not from any asset choice.

The served model is the cheap summary (the curve, whose midpoint moves with the mix's return and volatility); the simulation stays in the notebook as evidence.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Holdings and weights as a history | Weights are only in the Portfolio sheet, not Postgres | `wrangle` equity plugin, new table |
| Distributions and franking | Total return, not price | Fund registries |
| Return history for bonds, cash, property and gold as total returns | The defensive and diversifying side of the mix | `wrangle` interest table, fund data |
| Correlations by regime (calm, crisis) | One correlation understates diversification failure | Built from the history, including 2008 and 2020 |
| Spending history by category and the discretionary share | Whether you can cut | The costs sheet |
| Other income: Age Pension, super, rent, and their start dates | The income floor | Services Australia, super statements |
| Life tables | Survival, joint with your partner | ABS |
| Tax: marginal rates, franking, super tax, capital gains | After tax return | Your tax returns |
| Fees on each fund | Net return | Fund disclosures |
| Your risk aversion, elicited | `gamma` | The `portfolio/utility` questionnaire |
| Tolerance for a fall, in dollars | The drawdown constraint | A conversation, written down |
| Home equity and other assets, and whether they are in or out of the pool | What the mix has to carry | Your balance sheet |
| Forward capital market assumptions | Base for returns | Published assumptions |
| Joint monthly returns and inflation history | Block bootstrap | `wrangle`, ABS |
| Survival curve | Horizon | ABS life tables |
| Your minimum and discretionary spending | Whether a spending cut is possible | The costs sheet by category |

## Personal data

Real personal financial data MUST NOT be committed (`wrangle`'s rule, applied to `mlmodels`; see its `CLAUDE.md`). The `data/` captures of this workspace are git-ignored in the root `.gitignore`; the real inputs are your holdings, spending and elicited preferences, and none of them is recorded in a plan, a notebook or a test. What is committed here is synthetic, and the notebook rebuilds the placeholder when the files are absent. Check `git status` before staging.

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
