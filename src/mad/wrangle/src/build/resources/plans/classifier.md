# Bank classifier

## Model

| Field            | Rule                                                                                                                                                                       |
|------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Category Derived | Set only by the `Classifier` tab. Re-applied to every row, irrespective of Category Manual, after any classifier change or reprocess. Blank when nothing matches.          |
| Category Manual  | The only sticky cell. Set only by the operator, never by bank.                                                                                                             |
| Category         | Category Manual if set, else Category Derived.                                                                                                                             |
| Bucket           | Looked up from the category on the `Classifier` tab. Never stored, never clears a tick.                                                                                    |
| Vetted           | "Checked at the current category". Bank clears a tick whenever a row's category changes other than by the operator, so an unticked row needs looking at; `No` stays.       |

A row with Category Manual never changes category or loses its tick through the classifier; its Category Derived still tracks the
classifier, so Manual differing from Derived marks a live override and Manual equal to Derived a redundant one.

## Built

Parts A to D are built and released: classification, the hold, reporting and the backup lock. The sheet merge and the change
log were then replaced by `plans/flow.md` (3-way tab diff, operator-only change log), which `CLAUDE.md` describes. What
follows is still open.

## Part E: review of the blanked rows

1. Build a review CSV from the change log's `classifier` rows of every run since the release (the first standard run and the
   reprocess both contribute) into `Wrangle/Bank/archive/`, never the repo: Date, Account, Amount,
   Description, Category Before, Archive Category (the previous engine's name where it differs), Suggest, Push (operator marks `Y` or
   `N`), Transaction ID.
2. The operator marks it, or adds `Classifier` patterns instead; after a run, regenerate without rows that gained a category.
3. Apply the `Y` rows through the sheet, Category Manual and Vetted `Yes` in one edit so the tick holds; verify the next run merged
   them and Drive matches the sheet.

## Part F: ongoing clean-up

About 3,900 uncategorised rows, fixed by patterns where possible and Category Manual for one-offs. Each classifier edit applies on
the next normal run, its effect in the change log. Expected cost: about 3.5 MB of log in total, a 2–3 s upload per changing run, and
a self-expiring 30-day Drive version tail.

## Risks accepted

- A mistaken classifier edit clears ticks on the rows it moves; reverting restores categories but not ticks. The change log lists them.
- A tick set in the same run as a classifier edit that moves that row is cleared, and the row reappears unvetted.
- While an edit is held, new rows are classified by the previous classifier; a long-held edit delays its own effect, not other work.
  The live tab's buckets differ from the snapshot meanwhile, so every run rebuilds the state, a few seconds each, until the tab is
  fixed.
- A row that moves and moves back while its tab stays stale may be re-ticked by the guard-passing sheet value, at the category it was
  ticked at.
- An explicit Vetted `No` is cleared to blank when the row's category moves, since the judgement was about the old category.
