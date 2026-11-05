# runrate

The plan for the `finance_household_runrate` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/runrate/notebook.ipynb` |
| **Registered Model** | `finance_household_runrate` (`model.md` 6.1) |
| **Project Flavour** | `static` (`model.md` 3.2), target `local` |

**Status, 2026-11-05.** A placeholder. The notebook fits on a synthetic series, packages a `static` project, replays the golden and records it; the real series is not loaded yet and nothing is released.

## Intent

Separate the household's steady spending from its irregular spending, to give one baseline annual figure that the cost growth rate is applied to. The 4.83 percent growth is measured on everything, so it moves when a single large item falls in or out of a year; this notebook says what a normal year costs.

## What the data holds

The `Bank` workbook that `wrangle`'s `bank` plugin writes (tabs `Accounts`, `Classifier`, `Balances`, `Transactions_<year>` and the `Summary` and `Logs` outputs), on Drive under `Wrangle/Bank/release/data`. About 11,700 transactions across 13 accounts from 2021-05-01, when the statement history begins, to now, each with a `Category` (about 40) that the `Classifier` tab maps to a bucket. `bank` writes nothing to Postgres yet, so the first change for every household project is a `bank` table in `wrangle`'s schema, or a loader that reads the year files. The history is about 5 years, so the first year over year growth point is 2022-05 and there are fewer than 5 of them: the 4.83 percent is a short sample, compared above with the 40 year inflation window. Compare like with like (the 5 year inflation mean).

## Signature

| Direction | Name | Type | Notes |
|---|---|---|---|
| Input | `finance_household_runrate_in` | FP64 | Unused, required by the spec so the request is still validated |
| Output | `finance_household_runrate_normal_spend_dollars` | FP64 | Normal annual spend with the one-offs taken out, dollars. |
| Output | `finance_household_runrate_oneoff_allowance_dollars` | FP64 | Average annual spend on one-offs, dollars. |

`static` (`model.md` 3.2): the fitted numbers are the manifest's constants, and the simulation behind them stays in the notebook as evidence. It carries no evaluation (R14), so the check is the golden replay and the assertions in the notebook's Fit cell.

## Approach

1. **Explore.** Monthly spend by category as a table and a heat map, the transfers, interest and tax categories left out (`Bank Transfer`, `Credit Payment` and the `Excluded` bucket are movements of money and not spending).
2. **Find the one-offs.** Flag a category-month more than a robust threshold above the category's median (median absolute deviation), and every row over a stated amount. Look at them by hand, then write the rule into the `Classifier` or here.
3. **Compute the run rate.** Trailing twelve months of normal spend by category, summed, and its growth Y/Y with and without the one-offs. If the two growth rates differ, the single number was measuring the one-offs.
4. **Ship** the baseline annual spend and the one-off allowance as separate numbers.

This is exploration first. It is `local`, so other notebooks read its two constants from the committed `project/project.json` and nothing is served.

## Data to get

| Data | Why | Where from |
|---|---|---|
| A clean transfer flag, so movements between your own accounts never count | A transfer counted as spending doubles it | `Classifier` bucket `Excluded`, check it covers the transfers |
| Vetted flag on every closed month | Only vetted months are totalled | `Transactions` tab, `Vetted` column |
| Longer history | More than 5 years for growth | Older statements, if they exist (`Wrangle/Bank/archive`) |

## To do

1. Add a `bank` table to `wrangle`'s schema, or a loader for the year files.
2. Do steps 1 to 3 in the Explore section and note what the one-offs are.
3. Decide the threshold, then fit and write the golden samples.
