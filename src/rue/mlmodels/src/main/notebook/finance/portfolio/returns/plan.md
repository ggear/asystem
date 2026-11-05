# returns

The plan for the `finance_portfolio_returns` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `portfolio` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/portfolio/returns/notebook.ipynb` |
| **Registered Model** | `finance_portfolio_returns` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2) |
| **Consumers** | Served by `mlserver`. `pyfunc` is Python only, so there is no Rust or Go runtime |

**Status.** Placeholder. The notebook fits, accepts, packages and replays on a synthetic annual return series; the wrangle series is not loaded yet and nothing is released.

## Intent

Give one annual return per scenario to grow the portfolio to 2070. Placeholder: the base is the mean annual return and the low and high are one standard deviation either side.

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_portfolio_returns_scenario` | FP64 | Scenario, 0 low, 1 base, 2 high. |
| Output | `finance_portfolio_returns_nominal_pct` | FP64 | Annual portfolio return for the scenario, percent per year. |

`model.py` calls `set_model` and imports nothing beyond the base packages (`mlflow`, `numpy`, `pandas`) and the standard library, so the notebook declares no `PYTHON_DEPS` and `mlserver` needs no new package.

## Data

| Split | Dataset | Content |
|---|---|---|
| `training` | `portfolio_returns_training` | Ten years of annual portfolio return, synthetic around 6 percent with a 2.45 percent standard deviation. To be replaced by the portfolio built from `wrangle` |
| `validation` | `portfolio_returns_validation` | Five further years against the base scenario |
| `backtest` | `portfolio_returns_backtest` | Ten more years, held back for acceptance |
| `golden` | `portfolio_returns_golden` | Scenarios 0, 1, 2, rounding cases and out of range ones, then a request with the input missing, which must give a signature error |

The placeholder datasets are synthetic and committed, so `fab unittest` needs no database. The real sources are in the approach and the data to get below. `workbench.data` has `query_influxdb3` only: a `query_postgres` helper for `wrangle` is the first change before any of the real data can be loaded.

## Acceptance

The notebook owns the limits (`model.md` 6.8). Two gating checks on `finance_portfolio_returns_nominal_pct`: the `rmse` of the base scenario against the observed annual return on `validation` and `backtest` must not exceed 3.0 percentage points. One standard deviation of the placeholder is 2.45.

## Approach

Goal: one annual return for the portfolio to 2070, as a low, base and high scenario.

What `wrangle` holds today (checked against `src/mad/wrangle/src/build/resources/schema/postgres`): the `equity` table, one row per `(time, entity, type, period, unit)`, with `entity` a ticker and `type` including `price-close` and the 1, 30, 90 and 365 day `price-close-*-change-percentage`. The portfolio proxies are `MUS`, `MUK`, `MCK` and `MSG`, and the index funds are `VAS`, `VGS`, `VDHG`, `VHY`, `IAF`, `GOLD` and others. **There is no weights table in Postgres**: the weights come from the Portfolio sheet, `Indexes` tab, `Quantity` columns, which `wrangle` reads but does not store. The first step is to land those holdings in `wrangle` so weights are a queryable history.

The no risk anchor is already in Postgres: the `interest` table (`interest/rate`, from the Reserve Bank, sheet `Rates`) has entities `Bank`, `Inflation` and `Net`, each with the mean rate over 1, 5, 10, 20 and 40 years. `Bank` is the return with no risk, `Inflation` the matching price rise and `Net` the real return of cash. Those windows are the building block of the scenarios:

| Use | Reading |
|---|---|
| Floor of the low scenario | `Bank` mean at the longest window you believe, so low is cash plus a small premium and never below the no risk return |
| Base | `Bank` plus an equity risk premium times the share in risky assets, with the premium shrunk from the portfolio's own history toward a published figure |
| Spread of the windows | `Bank` at 5, 10, 20 and 40 years shows how far the no risk rate has moved between regimes, which is the honest width of the low to high range for the safe part |
| Real number | Use `Net`, or subtract the matching `household/costs` scenario by Fisher, so the return you plan with is the return after your own costs |

Terminology:

- **Total return against price return.** `price-close` leaves out distributions, which for `VAS` and `VHY` are several points a year. Price return understates the portfolio, and every number here must be total return (add distributions, or use an accumulation series).
- **Arithmetic against geometric mean.** The compound return is about the arithmetic mean minus half the variance (the **volatility drag**). Wealth grows at the geometric rate, so that is the single number.
- **Capital market assumptions.** A forward looking, building block estimate of each asset class: yield plus growth plus change in valuation (the Grinold-Kroner decomposition), not a historical average.
- **Sequence of returns risk.** The order of returns matters when you are spending. A single number hides it, which is why `portfolio/montecarlo` exists.

Method:

1. **Build the history.** Weights times asset total returns, monthly, converted to AUD with the `currency` table, net of fees. Report the portfolio's own volatility and drawdown, not just its mean.
2. **Forward base.** Blend the building block estimate with the history. Shrink the historical mean toward the capital market assumption, because 15 years of data cannot tell a 6 percent from a 7 percent return (the standard error of the mean is about the volatility over the square root of the years).
3. **Simulate to 2070.** Stationary block bootstrap of the monthly returns, with the mean re-centred on the forward base, so volatility and fat tails come from your data and the level from the assumptions. Take the compound rate of each path.
4. **Scenarios.** Base is the median compound rate and low and high the 25th and 75th percentiles. For named scenarios, move the drivers: a valuation reset, a lower growth world, a higher inflation world.
5. **Ship** the three numbers, and the real return by subtracting the matching `household/costs` scenario (Fisher), because spending is in costs.

Placeholder in this notebook: low and high are one standard deviation either side of the mean of ten synthetic years.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Portfolio holdings and weights as a history | Weights are not in Postgres, only in the Portfolio sheet `Indexes` tab | `wrangle` equity plugin, new table |
| Distributions and franking for each fund | Price return is not total return | Fund registries or an accumulation series |
| Total return history for bonds, cash and property | `IAF` is price only, there is no property series | `wrangle` interest table, fund data |
| Fees (management expense ratio) and tax drag | The return you keep | Fund disclosures, your tax return |
| Forward capital market assumptions | The forward base | Vanguard, JPMorgan or similar published assumptions |
| Valuation (cyclically adjusted price earnings, yields) | Mean reversion of returns | Public series |

## To do

1. Add `query_postgres` to `workbench.data` and load the real series in place of the synthetic ones.
2. Replace the placeholder fit with the method in the approach, keeping the signature.
3. Fix the limits against real data, then register and review before any release.
