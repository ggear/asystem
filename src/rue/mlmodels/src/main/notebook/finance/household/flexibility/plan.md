# flexibility

The plan for the `finance_household_flexibility` model. It follows `model.md`, the specification for MLflow model projects.

| Term | In This Plan |
|---|---|
| **Module** | `finance` |
| **Model** | `household` |
| **Notebook** | `src/rue/mlmodels/src/main/notebook/finance/household/flexibility/notebook.ipynb` |
| **Registered Model** | `finance_household_flexibility` (`model.md` 6.1) |
| **Project Flavour** | `pyfunc` (`model.md` 3.2), served by `mlserver` |

**Status, 2026-11-05.** A placeholder beside the other finance projects. The notebook, the directories and this plan are scaffolded; nothing is fitted or built.

## Intent

Split spending into essential, committed, discretionary and irregular, and say how much could be cut in a bad year. The Monte Carlo ruin probability is dominated by whether you can cut, so this is the second most valuable number after the cost growth rate.

## What the data holds

The `Bank` workbook that `wrangle`'s `bank` plugin writes (tabs `Accounts`, `Classifier`, `Balances`, `Transactions_<year>` and the `Summary` and `Logs` outputs), on Drive under `Wrangle/Bank/release/data`. About 11,700 transactions across 13 accounts from 2021-05-01, when the statement history begins, to now, each with a `Category` (about 40) that the `Classifier` tab maps to a bucket. `bank` writes nothing to Postgres yet, so the first change for every household project is a `bank` table in `wrangle`'s schema, or a loader that reads the year files. The categories (groceries, hospitality, lifestyle, subscriptions, home improvements, insurance, utilities, school, child care, holidays and the rest) are the raw material; the split is a judgement that has to be written down.

## Approach

1. **Classify the categories** by how fixed they are, using a table kept in the notebook: **essential** (cannot stop without harm), **committed** (contracts and fees you could end but not quickly), **discretionary** (can stop at once) and **irregular**.
2. **Check the classification against behaviour.** A category that fell sharply in a past month without harm was discretionary. The data shows which categories ever moved, which is better than opinion.
3. **Measure the cut.** The share of normal spending that is discretionary, and the largest fall in a twelve month sum seen in the history (the demonstrated flexibility).
4. **Ship** the essential floor and the discretionary share, for `portfolio/montecarlo` to use as a guardrail rule.

## Data to get

| Data | Why | Where from |
|---|---|---|
| Which spending is for the children and for how long | Child care and school end on a known date, which is a timing and not a cut | A conversation, written into the notebook |
| Contract terms (insurance, loan, subscriptions) | What is committed and until when | Statements |

## To do

1. Write the category table and run steps 2 and 3 on the history.
2. Feed the floor and share into `portfolio/montecarlo`.
