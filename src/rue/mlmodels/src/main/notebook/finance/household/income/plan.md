# income

The plan for the `finance_household_income` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/income/notebook.ipynb` |
| **Registered Model** | `finance_household_income` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2), served by `mlserver` |

**Status, 2026-11-05.** A placeholder beside the other finance projects. The notebook, the directories and this plan are scaffolded; nothing is fitted or built.

## Intent

Give the income that does not come from drawing down the portfolio: salary, dividends, interest, Age Pension and superannuation, as a path to 2070. `portfolio/withdrawal` and `portfolio/profile` need it, because spending covered by income is spending the portfolio does not have to fund.

## What the data holds

Income already lands in the `Bank` workbook categories (salary, dividends, interest, cash deposits). Superannuation and pension statements are in `Wrangle/Super` and `Wrangle/Pensions` on Drive (an AustralianSuper member transaction file and others are in the archive), and `wrangle` has no plugin for them yet.

## Approach

1. **Explore the income by category and year**, and the share that is regular against irregular.
2. **Retirement income path.** Age Pension (assets and income tested, with the rules in force and indexed), superannuation account balance and its tax free retirement income, rent if any. A model of the means test is a closed form function of assets and income, which suits a served model.
3. **Timing.** Start dates (preservation age, pension age) are known, so the path is deterministic; the uncertainty is in the rules, which is a scenario.
4. **Ship** the income at each age under low, base and high rules.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Superannuation balances and contributions | Part of retirement wealth and income | `Wrangle/Super`, a new plugin |
| Age Pension rates, thresholds and taper | The means test | Services Australia |
| Expected work income and end date | The accumulation phase | A decision, written down |

## Personal data

Real personal financial data MUST NOT be committed (`wrangle`'s rule, applied to `mlmodels`; see its `CLAUDE.md`). The `data/` captures and the `project/` of this workspace are git-ignored in the root `.gitignore` (`metadata.json` holds hashes and release state, no values, and stays committed), because the constants are derived from real spending and balances. What is committed here is synthetic, and the notebook rebuilds the placeholder when the files are absent. Check `git status` before staging.

## To do

1. Add a `super` loader to `wrangle`.
2. Write the Age Pension means test as a function and test it against the published examples.
3. Wire its output into `portfolio/withdrawal`.
