# Bank classifier rebuild and change log

## Model

| Field            | Rule                                                                                                                                                                       |
|------------------|----------------------------------------------------------------------------------------------------------------------------------------------------------------------------|
| Category Derived | Set only by the `Classifier` tab. Re-applied to every row, irrespective of Category Manual, after any classifier change or reprocess. Blank when nothing matches.          |
| Category Manual  | The only sticky cell. Set only by the operator, never by bank.                                                                                                             |
| Category         | Category Manual if set, else Category Derived.                                                                                                                             |
| Bucket           | Looked up from the category on the `Classifier` tab. Never stored, never clears a tick.                                                                                    |
| Vetted           | "Checked at the current category". Bank clears it whenever a row's category changes other than by the operator, so an unticked row means the row needs looking at.         |

A row with Category Manual never changes category or loses its tick through the classifier; its Category Derived still tracks the
classifier, so Manual differing from Derived marks a live override and Manual equal to Derived a redundant one.

## Part A: code

### A1. Classification (`_bank_transactions_classified`)

- The applied classifier is the snapshot `__bank_classifier.csv`, saved only at the end of a committed run, so a run dying part way
  leaves the old snapshot and the next run redoes the work; re-deriving is idempotent.
- On a `Classifier` change (live tab differs from the snapshot) or a reprocess (one path):
  - re-derive every non-placeholder row in every year file, matching once per unique description;
  - every row takes the new Category Derived, blank when nothing matches;
  - a row without Category Manual whose category changed loses its tick; a row with Category Manual keeps category and tick;
  - unchanged rows are not written, files with no changed row are neither written nor uploaded.
- On a normal run: re-derive every row in the changed files, not only uncategorised ones. With an unchanged classifier only rows whose
  own data changed can move (an edited manual-account description, a Redbark description going pending to posted), so Category
  Derived always matches the classifier and a moved row loses its tick.
- Hold: when the live tab raises any matching error (`CLASSIFIER_PATTERN`, `_PATTERN_CONFLICT`, `_TIE`, `_SHARE`, `_CODE_LIST`,
  `_CODE_ROWS`, `_BANK_CODE`, `_MERCHANT_CODE`, `_CATEGORY`, `_CATEGORY_CASE`), the edit is held: every run, normal or reprocess,
  classifies with the snapshot instead, the snapshot is not replaced, and a standing `Logs` error says the edit is held. `_TIE` and
  `_SHARE` surface only while matching, so derive first and decide before writing. Bucket-only errors do not hold, since they cannot
  move a category. With no snapshot (a fresh cache) and a held tab, nothing is classified until the tab is fixed.
- Remove the reprocess-only "keep the old category when nothing matches".

### A2. Sheet merge

- A tick is cleared only when the row's effective category (Category Manual, else Category Derived) changes and the tick was left as
  it was. Setting Category Manual to the category the row already shows, or clearing it when Category Derived equals it, keeps the
  tick.
- Stale-sheet guard: a sheet row's Vetted is not taken when it would re-tick a row (sheet `Yes`, file blank) whose sheet Category
  Derived disagrees with the file's. That row predates a move, from a tab whose upload was skipped as moved. An untick is always
  taken, so the worst case is a lost tick, shown as unvetted, never a wrong one.

### A3. Change log `bank_reclassified_<YYYY>_<MM>.csv`

- In bank's data folder, uploaded by the existing Drive sync. The month is the run's month by bank's clock, never the transactions';
  a month's file is appended to only during that month.
- One row per transaction or split part whose Category Manual, Category Derived or Vetted changed in the run.
- Columns: Run, Source (`classifier` or `sheet`), Year File, Transaction ID, Part, Date, Account, Amount, Description, Manual
  Before/After, Derived Before/After, Vetted Before/After, File MD5 (the year file as this run uploads it).
- Written after the year files are final and before the sync uploads; nothing when nothing changed, so an idle run or a reprocess
  with an unchanged classifier writes nothing.
- Skipped with a `Logs` error when the run's Drive sync reported an error, so a failed download cannot start a fresh local month file
  that overwrites the month on Drive. Those rows are the one gap, flagged.
- Never trimmed or deleted. New transactions are additions, held in the year files and backups, not the log.

### A4. Reporting

- Run log: classified, moved and ticks-cleared counts, and whether the live tab or the held snapshot classified.
- A `Logs` warning per year tab where rows moved: a new code, warning kind, not standing.
- A `Logs` error while an edit is held: a new code, error kind, standing until the tab is fixed.

### A5. Hygiene

- Root `.gitignore` gains `*bank_reclassified_*` before any fixture.

### A6. Consistent data backup

`src/build/resources/backup.sh` copies `data/` live: the install backs up before stopping the old container, and the supervisor's
nightly run backs up a running service, so a plugin run writing the year files mid-copy can leave a torn archive. `backup_written`
takes the run lock (`flock` on `data/wrangle-run.lock`, the same `fcntl.flock` file a run holds, shared across the container's bind
mount) with a bounded wait before `backup_files`, and releases it after, so the archive is always between runs. A wait timing out
fails the backup by name rather than copying mid-run. Keep `data/wrangle-run.lock` excluded, and run `shellcheck` on the snippet.

## Part B: tests

- Rewrite the cases asserting the old rules: forced reprocessing reclassifying every row, and a reprocess keeping an unmatched category.
- New synthetic cases:
  1. a classifier change moves a vetted row: tick cleared, logged;
  2. an unchanged vetted row: file not rewritten, nothing logged;
  3. a manual row: category and tick kept, Category Derived refreshed and logged;
  4. a row no longer matching is blanked;
  5. a bucket-only change clears no tick and regroups the totals;
  6. a normal run classifies an uncategorised vetted row and clears its tick;
  7. the stale-sheet guard;
  8. a merged sheet edit is logged with Source `sheet`;
  9. an idle run and an unchanged reprocess write no log;
  10. a month rollover starts a new file;
  11. a failed sync skips the log and raises the `Logs` error;
  12. Category Manual set to the row's current category keeps the tick; set to a different one without ticking clears it;
  13. a normal run re-derives an edited row in a changed file and clears its tick, leaving the file's other rows alone;
  14. a tab with a pattern conflict holds the edit: rows keep the snapshot's categories on a normal run and a reprocess, the snapshot
      is kept, the held error stands, and fixing the tab applies the edit on the next run;
  15. the guard blocks a stale re-tick and takes a stale untick;
  16. the release order, a standard run then a reprocess then a standard run, with an unchanged tab: the moves land across the first
      two and the third moves nothing and writes no log.
- Run the bank tests, plus the preview and release replays.

## Part C: docs

Wrangle `CLAUDE.md` Bank section: the model, the change log and its never-delete rule, and that a classifier edit takes effect on the
next normal run, no reprocess needed.

## Part D: rollout

1. Check the latest run raises no standing `CLASSIFIER_*` error, or the release's rebuild is held. Optionally name the bank sheet's
   current version (UI only).
2. Review, stage and commit the change.
3. Release. The sequence, from `install.sh` and `install_post.sh`:
   1. load the image, then back up the running version's `data/` (`BACKUP_SKIP_HOURS=0`, never skipped; a failed backup abandons
      the install and leaves the old version running);
   2. stop the old container, copy its home into the new version's, start the new container;
   3. the poller's first run starts at once, a standard run (`--disable-reprocessing`), with the snapshot carried over and an
      unchanged tab, so it re-derives only changed files and may already blank a few no-match rows there;
   4. `install_post.sh` runs `wrangle --enable-uploads`, a separate process that reprocesses with Drive downloads and all uploads on;
      it queues on the run lock behind the standard run, then re-derives every row, blanking the rest of the rows no current rule
      matches (about 1,350, all vetted history), logging each;
   5. the poller's standard runs resume every 30 minutes.
4. Verify, run by run:
   - install output: the backup started from the running version and its archive lists `data/bank/redbark_transactions_*` and
     `__bank_classifier.csv`, well over the 44 KB of the pre-bank archives. No archive holds bank data before this release, so this
     is the first;
   - first standard run and the reprocess: moved rows summed across both about 1,350, every one vetted to blank, unvetted up by
     the same count, no other category moved, the change log holding the same rows as `classifier`, Drive matching the sheet;
   - the next standard run: nothing moved, no change-log rows, no year file uploaded, which proves re-deriving is idempotent.
5. Verify the next 01:00 supervisor run (`/home/asystem/supervisor/backup/<run>/run.log`): primary exported `wrangle` from the new
   version as `success`, secondary promoted it to `/share/10/backup/wrangle` and thinned with the module pruner, tertiary snapshotted;
   the archive lists `data/bank` with the change log.

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

## Backups relied on

| Tier      | Where                                                                    | Retention                                  |
|-----------|--------------------------------------------------------------------------|--------------------------------------------|
| Primary   | `/home/asystem/wrangle/backup`, nightly at 01:00 and per new version     | 7 days                                     |
| Secondary | `/share/10/backup/wrangle`, promoted nightly by the supervisor           | GFS: 7 daily, 13 weekly, 1,200 monthly     |
| Tertiary  | `/backup` disk, mirrored nightly with read-only snapshots                | mirror plus read-only snapshots            |

The module's `backup.sh` writes primary (its includes are `data/bank` and the three history files), and the supervisor's nightly run
promotes and thins; all three stages reported `success` the night before this plan. Every stage includes `data/bank`, so the change
log and the classifier snapshot too, and `restore.sh` restores `data/bank` whole. Long-term history is the nearest backup plus replaying the change log; the File MD5
pins a row to an exact Drive version within Drive's 30-day window.

## Risks accepted

- A mistaken classifier edit clears ticks on the rows it moves; reverting restores categories but not ticks. The change log lists them.
- A tick set in the same run as a classifier edit that moves that row is cleared, and the row reappears unvetted.
- A failed Drive sync drops that run's change-log rows, flagged by a `Logs` error.
- While an edit is held, new rows are classified by the previous classifier; a long-held edit delays its own effect, not other work.
  The live tab's buckets differ from the snapshot meanwhile, so every run rebuilds the state, a few seconds each, until the tab is
  fixed.
- A row that moves and moves back while its tab stays stale may be re-ticked by the guard-passing sheet value, at the category it was
  ticked at.
- An explicit Vetted `No` is cleared to blank when the row's category moves, since the judgement was about the old category.
