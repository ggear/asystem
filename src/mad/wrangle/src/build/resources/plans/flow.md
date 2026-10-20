# Bank run flow: sheet, Redbark, classifier, state, Drive

A plan, not built. No merchant, amount or id appears here.

## 1. What is wrong today

1. **Sheet edits are missed after a recent write (the reported bug).** `sheet_download` (`_sources.py:669`) asks Drive for the
   spreadsheet's `version` and serves every tab from cache when `_sheet_<tab>_v<version>.csv` already exists. Drive's `version`
   for a Sheet lags edits by minutes. Release, 20 Oct: the 09:23:50 run downloaded at `v781`, its uploads at 09:23:57 and
   09:24:01 read the version back as `v781` again, and the 09:25:44 run (a reprocess) reported `Sheet tabs [9] status [CACHED]`.
   Any edit in that window is not merged (`bank.py:1080`, `if sheet_downloaded`), so the CSV is not written, not classified and
   not synced. It is merged on a later run only if the version moves before the next upload.
2. **The same lag can overwrite an edit.** The upload guard `_sheet_moved` (`_sources.py:1397`) calls the same `sheet_download`,
   gets `CACHED`, decides the tab has not moved and uploads over the operator's edit.
3. **Files changed on Drive are committed but not classified** (`bank.py:1739` classifies only `files_changed`, the files the
   run wrote). That is why hand-added rows need a reprocess.
4. **Drive upload is unconditional.** `drive_synchronise(upload=True)` (`_sources.py:1327`) uploads whatever differs from the
   listing it took at the start of the upload call, so an edit saved on Drive while the run worked is replaced.
5. **Drive change detection trusts timestamps.** A download is taken when Drive's `modifiedTime` is later than the local mtime
   (`_sources.py:1267`), and an upload stamps Drive with the local mtime. A local write that failed to upload, followed by a Drive
   edit stamped earlier, is never pulled; a duplicate file name on Drive is silently collapsed to one.
6. **The sheet merge compares the tab against the files**, never against the tab as the plugin last saw it. A stale tab (an upload
   skipped as moved) or a file changed on Drive therefore reads as an operator edit and needs special cases (`_bank_vetted`'s
   re-tick guard, `__editable`, the `ACCOUNT_LINKED` checks), and an edit whose id no longer exists is dropped silently
   (`bank.py:1198`).
7. **Redbark 429s are logged, not retried** (`_sources.py:222`).
8. **Gone, relisted and `Date Posted` checks stop at the add window** (about two weeks).
9. **Manual (AMEX) rows and balances are entered on the sheet**, which is most of the merge code: name resolution, new-row
   grouping, moves between year files, monthly placeholders, and a separate balances merge.

## 2. Principles

1. **The year CSVs on Drive are the golden copy.** The local cache is a working copy, the sheet is a view of the files plus an edit
   channel for three columns. Everything on the sheet can be rebuilt from the files.
2. **Each column has one writer**, so merge order never decides a value:

   | File | Column | Written by |
   |---|---|---|
   | `redbark_transactions_*` | Date, Amount, Description, Bank Code, Merchant Code, Account ID | Redbark, once, when the row is added |
   | `redbark_transactions_*` | Source ID, Date Posted (and Date, once, with it) | Redbark adoption |
   | `manual_transactions_*` | Date, Account, Amount, Description, Account ID | the operator, on Drive |
   | all transactions | Category Derived | the classifier |
   | all transactions | Category Manual, Amount Split and split parts | the sheet |
   | all transactions | Vetted | the sheet; the classifier only clears it, on a move not made by the operator |
   | `redbark_balances_*` | every column | Redbark |
   | `manual_balances_*` | every column | the operator, on Drive |

   The operator may still rewrite any column of any file on Drive by hand (history fixes); the run takes that file as given.
3. **One change signal.** A file is changed when its MD5 differs from the MD5 recorded at the last successful Drive sync. That one
   set drives classification, state, tab uploads and the Drive sync, whatever changed the file: Drive, the sheet, Redbark, the
   classifier.
4. **A sheet edit is a difference between two versions of the tab**, the one downloaded now and the base, the last one the plugin
   downloaded and fully persisted, or uploaded itself. Only cells that moved between the two are edits, so a stale tab or a file
   changed on Drive can never be mistaken for one.
5. **Commit last, and only what was persisted.** The tab bases, the classifier snapshot, the accounts snapshot and the sync manifest
   move forward only after the files they produced are on Drive. A run that dies, or a file whose upload is skipped, leaves them
   where they were, and the next run redoes the work. Every step is idempotent.

## 3. Plugin flow, common to every plugin

Every plugin file opens with this header, its blocks numbered and named, and each block in the code starts with the same one-line
`# <n.m> <Label>` comment. Sections a plugin does not use are listed as `none`, so the numbering is the same everywhere.

```
# Flow, every run in this order; [R] marks what a reprocess changes, [F] what --force-downloads changes.
#
# 1 Download: bring every source into the cache.
#   1.1 Download Drive    pull files whose Drive MD5 moved since the last sync
#   1.2 Download Sheet    read the input tabs, a new local version where a tab's content changed
# 2 Load: parse the operator's dimension tabs.
# 3 Merge: apply operator edits to the golden files.
# 4 Fetch: add upstream data to the golden files.
# 5 Derive: compute plugin-owned columns in the files.
# 6 Commit: state_cache each partition, giving its delta.                    [R] rebuild every partition
# 7 Check: raise data problems to Logs.
# 8 Sync: push changed files to Drive, skipping any Drive changed mid-run.  [R] verify every file
# 9 Upload: write the delta to the database, each partition's tab to the sheet.  [R] every tab
# 10 Snapshot: move the bases forward for what was persisted.
```

Mapping of today's blocks: currency and interest are `1.x Download Rate Data`, `5 Derive (Process, Normalise)`, `6 Commit`,
`9 Upload`, sync in `Plugin.run`; equity is `1.1 Download Stock and Fund Data`, `1.2 Download Index Data`, `5 Derive (Collect,
Process, Enrich)`, `6 Commit`, `7 Verify`, `9 Upload`. Only labels and the header change in those three.

## 4. Bank, standard run

1. **Download**
   1. *1.1 Download Drive.* `drive_synchronise(download=True)` against the manifest (section 6.2). Each file logs `downloaded`,
      `cached` or `conflicted`.
   2. *1.2 Download Sheet.* One `batchGet` of `Accounts`, `Classifier` and every `Transactions_<year>` tab, always (about 2 s more
      than today's version check, and no lag). Each tab whose content differs from its latest local version is written as
      version n+1 (`downloaded`), else `cached`. `Balances` is no longer read.
2. **Load**
   1. *2.1 Load Classifier.* As today: parse, raise matching errors, decide changed and held against `__bank_classifier.csv`.
   2. *2.2 Load Accounts.* As today, including the weekly and on-edit Redbark accounts call and the `Accounts` cell writes.
3. **Merge**
   1. *3.1 Normalise Files.* For each changed `manual_*` file (and every one on a reprocess): fill a blank Account ID from the
      Account name against the Manual accounts (today's `_bank_accounts_resolved`), Amount Split from Amount, and validate (date,
      amount, decimals, zero, description, future, before `From`, duplicate). A file with an invalid row is left untouched on disk and
      errored by row, so the operator's text is never rewritten. Its **whole year** is then left as committed in 6 (both families):
      replacing the year's partition without that file would delete its rows from the state. A file saved by Excel or Sheets is read
      as such: a BOM, CRLF line endings, `dd/mm/yyyy` dates, and `$` or `,` in amounts.
      `manual_balances_*` normalise the same way. The operator writes Date, Account and Balance Manual, with Time optional
      (default `23:59:59`). The run fills Account ID, Balance and Time, and validates sign, jump, future, before `From`, and
      duplicates, as the sheet merge does today. Normalising is idempotent: a second pass writes the same bytes.
   2. *3.2 Merge Transactions Tabs.* For each tab with a new version, diff it against its base (`__bank_tab_<tab>.csv`) per
      Transaction ID:
      - an id's parts are compared as a set of (Amount Split, Category Manual, Vetted), never by row position, so sorting or
        filtering the tab cannot move an edit onto another part;
      - a set that differs replaces the file's parts for that id with the tab's, after the sum and sign checks. One part is the
        common case: a plain Category Manual or Vetted edit;
      - the formula columns (Category, Bucket) are never diffed, since they change whenever the Classifier tab does;
      - any other column that moved is not taken: one `TAB_EDIT_IGNORED` error per tab, and the re-render in 9 puts it back;
      - an edited id no file holds is looked up by Source ID, then by account, cents and three days when that gives exactly one
        row. That covers an id that changed under the tab: Redbark adopting a Date, or a Drive edit. Still unmatched →
        `EDIT_UNMATCHED`, never dropped silently;
      - the edit is applied to the file row. The sheet wins over whatever the file holds in those columns.
      Every comparison is on typed values from the tab schema, never on raw text: cents for amounts, ISO dates, stripped
      strings, `Yes`/`No`/blank for flags (`sheet_upload`'s `_tab_typed`). The sheet displays `1,234.00` where the upload wrote
      `1234.0`, so a text compare would see an edit after every upload. A row with no Transaction ID (a manual row typed on the
      sheet out of habit) is one of the ignored edits, and its error says manual rows go in files on Drive.
      With no base (a fresh cache), the base is the tab rendered from the files, which is today's behaviour. A tab cut short by a
      failed upload only has missing rows, and a missing row is never a deletion, so it yields no edit.
4. **Fetch**
   1. *4.1 Fetch Balances.* As today, three-hourly, appended to `redbark_balances_<year>` by Balance ID.
   2. *4.2 Fetch Transactions.* As today (moved or daily trigger, add window from the account's latest held row less 14 days, adopt
      by source id, else by account, cents and three days). Weekly, the check window widens to 90 days (section 6.4).
   3. *4.3 Import Exports.* Rename each new `activity*.csv`, then merge every new or changed export into the manual year files
      (section 7).
   4. *4.4 Dedupe Transactions.* As today, over changed files.
5. **Derive**
   1. *5.1 Classify Transactions.* Every file when the `Classifier` tab changed (or on a reprocess), else every changed file, by the
      one change set, so Drive edits, sheet edits and new Redbark rows are all classified. Hold rules unchanged.
6. **Commit**
   1. *6.1 Commit Balances.* One `state_cache` (`bank_balances`), rebuilt when a balances file or the accounts changed.
   2. *6.2 Commit Transactions.* One `state_cache` per year (`bank_transactions_<year>`) for each changed year, every year when the
      accounts or the classifier's buckets changed. Each returns that year's delta. Replaces today's single state with `replace=`.
      Each year's update replaces its partition whole (`replace=pl.lit(True)`). Without that, `state_cache`'s coalescing merge
      would keep a row deleted from a file: by the operator on Drive, by dedupe, or by a conflict that rolled back to Drive's
      version. 6.1 does the same for balances.
7. **Check**
   1. *7.1 Check Accounts.* As today (unmapped, shared names, two accounts, manual stale, reconcile).
   2. *7.2 Check Transactions.* As today (unclassified, unvetted, unbucketed).
8. **Sync** (before the tabs, so a tab only ever shows what reached Drive)
   1. *8.1 Sync Drive.* Bank calls `drive_synchronise(upload=True)` itself, so the result is known before 9 and 10. Each changed
      file is `uploaded`, or `conflicted` when Drive moved since 1.1 (section 6.2). `Plugin.run`'s closing sync then finds
      nothing to do.
9. **Upload**
   1. *9.1 Upload Balances Tab.* When the balances delta is non-empty, or the tab differs from its render.
   2. *9.2 Upload Transactions Tabs.* For each year whose delta is non-empty, or whose tab differs from its render (a rejected edit,
      a part-written upload), and none of whose files `conflicted`. Each tab is re-read just before it is written and skipped as
      `moved` if it changed since 1.2; it is then merged next run. Only the one or two tabs actually written pay that read.
      `sheet_upload`'s own content check still skips a no-op.
      The tab's blue operator cells and dropdowns follow the new editability: Amount Split, Vetted and Category Manual only. The
      blue Account-to-Description cells on manual rows go, and so do the Balances tab's blue `Balance Manual` column and its
      `Balance` formula's manual branch, which still renders but is no longer an input.
   3. *9.3 Upload Summary Tab.* The `Transactions` monthly tab, as today.
   4. *9.4 Upload Logs Tab.*
10. **Snapshot**
    1. *10.1 Commit Bases.* Copy each tab's content to `__bank_tab_<tab>.csv`, right after its upload or skip:
       - the version just uploaded, if it was uploaded;
       - else the version downloaded in 1.2, provided every file its edits went into reached Drive. This holds even when the
         upload was skipped as `moved`: the 1.2 edits are persisted, and the mid-run edit then shows as a difference from that
         version next run. Keeping the old base there would replay the 1.2 edits and re-tick any row the classifier cleared in
         between;
       - else, when a file its edits went into `conflicted`, the base stays where it was, so those edits replay onto Drive's
         version.
       Bank keeps this pointer itself, so `_sources.py` needs to keep only the latest version of a tab. Write the classifier and
       accounts snapshots as today, unless a file they changed `conflicted`.
    2. *10.2 Log Changes.* Append this run's operator-state changes to `bank_reclassified_<YYYY>_<MM>.csv` (section 8), for
       files that reached Drive only. `Plugin.run`'s closing sync uploads it.

## 5. Reprocess and force downloads

- **Reprocess** is the standard run plus: normalise every manual file (3.1), classify every file (5.1), rebuild every state (6),
  upload every tab without the content check (9), and compare every file with Drive (8, free from the listing). Tab edits are
  merged first, as always, so a reprocess never overwrites a pending edit.
- **`--force-downloads`** refetches every account's whole history to check held rows, as today, and adds nothing outside the add
  window.
- **`--force-uploads`** stays the only way to re-upload a Drive file whose bytes are already there.

## 6. Shared changes in `_sources.py`

1. **`sheet_download` by content.** Drop the Drive version lookup. Read the tabs, compare each with its latest
   `_sheet_<tab>_v<n>.csv`, write v<n+1> only on a difference, and return one `DownloadResult` per tab in a dict when given a list,
   so each tab carries its own `DOWNLOADED` or `CACHED`. `sheet_upload` writes its upload as the next version. Cleanup keeps the
   latest two versions, since bank keeps its own bases. Equity's single-tab calls keep working.
2. **`drive_synchronise` by manifest.** Its return type changes, so equity's caller (`equity.py:366`), which reads
   `(present, downloaded)`, moves to the per-file status in the same change, and so do the tests. `_drive_synced.json` in the cache (underscore-prefixed, so never synced) holds each file's
   MD5 at its last sync.
   - Download: Drive MD5 differs from the manifest → download. Local also differs → `conflicted`: Drive wins, the local work is
     redone next run, a `DRIVE_CONFLICT` error.
   - Upload: re-list Drive first. Local MD5 differs from the manifest and Drive's does not → upload and record. Drive's differs too
     → `conflicted`, skipped, error.
   - A name listed twice on Drive → `DRIVE_DUPLICATE` error and that name is left alone.
   - A file equal on both sides is always recorded, on any run. That makes the manifest self-healing after a run killed mid-sync.
     With no manifest at all, a file that differs is decided once by today's timestamp rule.
   - The manifest is rewritten atomically (temp file, then rename) after each upload, never only at the end.
   - Names a plugin marks download-only (bank: `activity*.csv`, `amex_*`) are never uploaded. This is a `Plugin` attribute, so
     `Plugin.run`'s closing sync honours it too, not just bank's own call.
   - Mtimes are still stamped both ways for people looking at them, never used to decide.
   - Returns per-file status (`downloaded`, `cached`, `uploaded`, `verified`, `conflicted`) instead of `(present, downloaded)`.
3. **Redbark backoff.** On 429 or 503, wait `Retry-After` (seconds or a date), else 5 s doubling, at most 60 s a wait and 4 retries,
   inside a 3-minute budget shared by the whole run (not per call, or a sweep across 8 accounts could pass the 10-minute run
   timeout); when `X-RateLimit-Remaining` reaches 0, wait for `X-RateLimit-Reset` before the next request.
   Each wait logs at `warn`; a call that still fails returns its error as today.
4. **Weekly sweep.** `TRANSACTIONS_SWEEP_DAYS = 90`, `TRANSACTIONS_SWEEP_EVERY_DAYS = 7`, due by the mtime of
   `_redbark_transactions_sweep.csv`, which is stamped when a sweep is **attempted**, even when an account's call fails. Otherwise
   one failing account would make the 90-day fetch due on every run and drive the rate limit. The fetch's `from` widens to 90 days; gone, relisted and
   `Date Posted` adoption run over the whole check window, while new rows are added only inside the add window. A Redbark row
   in the check window with no held match raises `TRANSACTION_UNHELD` instead of being added. Outside the add window, a fuzzy
   relisting (account, cents, three days) is adopted only when it pairs one to one. A same-amount repeat, such as a daily coffee,
   raises `TRANSACTION_RELISTED` with no adoption, so 90 days of recurring charges cannot swap ids.

## 7. AMEX imports

AMEX has no Redbark feed, so its transactions come from the activity exports AMEX's site downloads, dropped into the bank's synced Drive data
folder (`Wrangle/Bank/<scope>/data`, beside the year files). Every export is kept for good, renamed, as the record of what AMEX listed; the year files hold the rows and the operator's
columns.

### 7.1 What the exports look like

From the two release exports (`activity.csv`, `activity-2.csv`), read for shape only:

- Header `Date, Date Processed, Description, Card Member, Account #, Amount`, UTF-8 with a BOM, no newline after the last row.
- Dates `dd/mm/yyyy`, newest first. `Date Processed` is 0 to 6 days after `Date`, so it is `Date Posted`.
- Charges are positive and credits negative, the reverse of the year files, so the amount is negated.
- `Account #` is a 5-digit per-card suffix (`-NNNNN`), **not** the account number on the `Accounts` tab. Each export holds two cards
  (a primary and a supplementary member), one account.
- Descriptions carry runs of spaces (most rows). Each export has 7 rows identical to another on the same day: real repeat purchases,
  which dedupe must keep.
- The two exports are two different accounts, one per AMEX row on the `Accounts` tab, and each overlaps the history already held on
  its account almost completely: on date, cents and description, 1268 of `activity.csv`'s 1271 rows and all 339 of
  `activity-2.csv`'s are held rows. That history is mostly in the `redbark_transactions_*` files, with Category Manual and Vetted set
  on many rows and `Date Posted` blank on some. The 3 unmatched rows in `activity.csv`, dated 8 to 12 days before its last day, are
  genuinely missing from the files: two have no held row of the same cents within 5 days, and the third is a second purchase of
  the same amount on a day whose other purchase is held. The import adds all three. The one held row in the span that the export
  does not list is the October placeholder (amount zero, on the 1st), which 3.1 drops before the import, so it raises no
  `IMPORT_GONE`. `activity-2.csv` matches exactly.

### 7.2 Mapping an export to an account

No new column, and no new `Accounts` row or `From`. A card's number is not part of any account's identity, so a reissued card
changes nothing. The account is found in this order:

1. **By file name.** An export already renamed to `amex_<number>_transactions_<date>.csv` belongs to the account with that `Number`.
   The name is the mapping, so the operator can also name a file by hand.
2. **By card.** Every renamed export keeps its `Account #` column, so a card seen in one names its account. All of an export's known
   cards must agree.
3. **By overlap with held rows.** An export with no known card belongs to the one AMEX account that holds at least half of the
   export's rows dated on or before that account's newest held row, matched on date, cents and canonical description. On the
   release exports this is 1268 of 1271 and 339 of 339 rows, against none on the other account.

The account must be `Manual` or `Closed`, else `ACCOUNT_LINKED`. With no match, or more than one, the export is left as
`activity*.csv` with `IMPORT_UNMAPPED`, and the operator renames it by hand once. That only happens for a new card whose first
export starts after everything held, so each download should overlap the last one by a few days.

A one-off history rewrite is not needed for matching. Section 7.4 fills the blank `Date Posted` values on its own, and held rows
stay in whichever file holds them.

### 7.3 Rename

- `activity*.csv` (any case) is an export not yet renamed. It is renamed to `amex_<number>_transactions_<last>.csv`: `<number>` is
  the account's `Number` on the `Accounts` tab (`xxxx1000`), `<last>` the newest `Date` in the export (`2021-12-31`).
- A taken name gets `_2`, `_3` and so on, even for a byte-identical re-download: nothing is deleted, and dedupe makes a repeat
  harmless.
- An export with a wrong header, an unparsed date or amount, or an amount with more than two decimals is left unrenamed and
  unimported with `IMPORT_UNREADABLE`, so the operator can fix or replace it. Never partially imported.
- The rename is one `_sources.py` step, `drive_rename`, run in 4.3 rather than deferred to 8 Sync:
  1. On Drive, by **file id** from 1.1's listing: `files().update(fileId, body={"name": new})`. Drive keeps the id and the revision
     history, so the rename deletes nothing. Because it goes by id, two files both called `activity.csv` are fine: each is
     renamed on its own, and `DRIVE_DUPLICATE` does not apply to `activity*.csv`.
  2. Locally, `os.rename` of the cached copy.
  3. The manifest entry moves to the new name, so 8 Sync sees neither a missing nor a new file.
- If the Drive rename fails, nothing has changed: an error is raised, and the next run retries.
- Exports only ever flow from Drive to the cache. 8 Sync never uploads an `activity*.csv` or an `amex_*` file. So if step 2 or 3 fails
  after Drive was renamed, the stale local copy is never pushed back. The next run downloads the new name, and a local
  `activity*.csv` whose MD5 equals a renamed export's is ignored.
- A run that dies after renaming leaves the rename done. The next run maps the file by its name and imports it as new.
- With Drive uploads disabled (tests, a local run), only the local copy is renamed, and the next service run renames it on Drive.
- A hand rename is just the operator renaming the file on Drive to the `amex_` form. The plugin validates the name (a known
  `Manual` or `Closed` AMEX `Number`, a date) and otherwise treats the file as an export not yet renamed.

### 7.4 Merge into the year files

- Each export row becomes a manual row: `Date`, `Date Posted` from `Date Processed`, `Amount` and `Amount Split` the negated amount,
  `Description` stripped (inner spaces kept; the id canonicalises them), the account's name and Account ID. `Card Member` and
  `Account #` are never stored or logged.
- Rows are identified exactly as every transaction is: `bank_transactions_identified` over account, date, cents, description and
  the ordinal among identical rows. The ordinal is what keeps same-day repeats: two identical charges are ids `…0` and `…1` in
  every export that covers that day.
- **Adding a row never changes an existing row's id.** Ordinals are counted over a year's rows in a fixed order: `redbark_*`
  first, then `manual_*`, each in file order, and new rows always append to the end of `manual_*`. Today's collect and merge put
  `manual_*` first (`bank.py:1947`, `_bank_year_paths`). So appending a repeat to the manual file, when its twin is held in a
  redbark file, would swap the two rows' ids along with their operator columns. Flipping the order may re-id the few existing
  identical pairs split across families once; count them on release data before the change, and the pinned ids must still pass.
- Export rows with a blank `Date Processed` are pending: skipped and counted in the file's log line, never imported, since a
  pending charge can change amount or description before it posts. The release exports have none.
- **Dedupe is a union by Transaction ID** over every export and the held rows: an id already held is left exactly as it is
  (Category Manual, Vetted, split parts, which share the id), apart from a blank `Date Posted` being filled. An id not held is
  appended to `manual_transactions_<year>.csv`. So overlapping exports count a transaction once, never twice, and an export that
  starts later than the history never removes anything.
- A held row on the account, strictly inside an export's date span (its first and last days excluded, since an export downloaded
  mid-day lists only part of its last day), that no export lists raises `IMPORT_GONE` (a reversed charge, or a row
  typed by hand differently). A new row within three days and the same cents as a held row with another id raises `IMPORT_SUSPECT`
  (a hand-entered duplicate). Neither deletes anything; the operator does on Drive.
- Imported rows are then classified, committed, rendered and synced like any other change.

### 7.5 When an export is read

- **Standard run:** only an export that is new or changed by the manifest rule, and a just-renamed one counts as new.
- **`--force-downloads`:** every export, which is the "read every source again" lever, as it is for Redbark.
- **Not on reprocess.** A reprocess rebuilds from the held files and refetches nothing. Reading every export would also bring back a
  row the operator deleted from a year file, which should take an explicit `--force-downloads`, where the run logs each file's
  `added [n]`. Otherwise re-reading is harmless, since the union is idempotent.

### 7.6 Git and personal data

- Root `.gitignore` gains `activity*.csv` and `*amex_*` ahead of any fixture; the existing exception for `local/bank/*/data/*`
  keeps the synthetic fixtures committed. Check both with `git check-ignore` before the first fixture.
- Synthetic exports only in local fixtures (`Bank A`-style names, `-00001` cards, made-up merchants). Real exports live only on
  Drive and in the preview and release fixture `data/` dirs, which are already ignored.

## 8. Change log

`bank_reclassified_<YYYY>_<MM>.csv` stays, narrowed to what nothing else records.

### 8.1 Why keep it

Release, October 2026: 7594 rows over 89 runs.

| Source | Changed | Rows |
|---|---|---|
| classifier | Derived only | 2613 |
| classifier | Derived and Vetted (tick cleared) | 1624 |
| sheet | Manual | 1867 |
| sheet | Vetted | 1296 |
| sheet | Manual and Vetted | 194 |

- The classifier cleared 1624 ticks in one month. Clearing a tick is the one place the plugin destroys operator state, and the log
  is the only practical record of which rows lost one. Getting the same answer from Drive revisions or backups means diffing
  many file versions.
- It is also the audit trail for "did my edit land", which is the bug that started this plan.
- Drive revisions and backups remain the way to restore a file. The log is the index into them (Run, File MD5).

### 8.2 What changes

1. **Operator columns only.** A row is logged when Category Manual, Vetted or split parts change. Derived-only rows go (a third of
   the volume): Category Derived is a pure function of the row and the Classifier tab, so reverting the tab reverts it, and the
   `Logs` warning per year tab already counts moved rows. Derived Before/After stay as context on rows that are logged.
2. **Splits recorded.** Add `Split Before` and `Split After` (Amount Split). Parts are paired by ordinal when the count is unchanged.
   Otherwise each removed part is a row with blank After, and each added part a row with blank Before.
3. **Sources:** `sheet` (an edit applied by 3.2) and `classifier` (a tick cleared by 5.1). No `drive` source: a hand edit on Drive is
   in Drive's own revision history, and logging it would need the pre-download copy kept aside. Imports and Redbark touch no
   operator column, so they log nothing.
4. **Written after 8 Sync, for files that reached Drive** (step 10.2). A conflicted file's changes are not written; they are logged
   when they replay next run. The log therefore never claims a change that was rolled back, and File MD5 always names a Drive
   revision.
5. **`CHANGES_UNLOGGED` and its `drive_failed` guard go.** They existed so a failed download could not start a fresh local month
   file that overwrote Drive's. The manifest now downloads Drive's month file first and refuses an upload over a Drive change,
   so that cannot happen.
6. **Unchanged:** one file per month of the run's clock, appended only in that month, never trimmed or deleted, nothing written by
   an idle run.

### 8.3 Existing files

- **Dropped at the cutover (section 11), not rewritten.** Every existing `bank_reclassified_*` file is removed from Drive and the
  cache, and the log starts empty on the first run of this release, in the new format only.
- **Why drop rather than rewrite:** the old rows came from the old merge, which compared tabs against files. Some of October's 1867
  `sheet` rows are likely stale-tab replays rather than real edits, and their File MD5s point at revisions the cutover's reprocess
  supersedes. Converting them would carry that residue forward.
- **Nothing tolerates the old header,** because none survives, and the code has no migration path. Before the drop, a copy goes
  into the cutover archive (11.2), outside Drive's data folder and the cache.

`classifier.md` A3 is rewritten to match in build step 7 (11.1).

## 9. Logging

- One line per file per stage that acted, at `info`, in the `_sources.py` form `File [<name>] <verb> ...` with its own time:
  `downloaded`, `cached` (debug), `normalised`, `merged [n] edits`, `fetched [n] new [n] adopted`, `renamed to [<name>]`, `imported [n] added [n] held [n]`, `deduped`, `classified [n]
  moved [n] ticks cleared [n]`, `committed delta [n]`, `uploaded`, `verified` (debug), `conflicted`. Tabs use
  `Sheet [Bank:<tab>] <verb>`: `downloaded version [n]`, `cached`, `merged [n] edits [n] ignored`, `uploaded`, `unchanged` (debug),
  `moved`.
- Each block keeps its closing summary line, timed from the block's own start, so no time is counted twice.
- Idle runs stay short: the per-file lines that would say nothing happened are debug.

## 10. Tests

- **Local** (offline, cached tabs and Redbark replay, as today), one case each:
  1. Category Manual edited on a 2026 tab, nothing else: the file takes it, is classified, committed, synced; the tab is not
     re-uploaded. Run twice: the second run does nothing. Repeat with Drive's version unchanged since the last run, the case
     today's code misses.
  2. Vetted tick and untick; a split added, changed, removed; an invalid split kept off.
  3. A Description edited on a linked row: `TAB_EDIT_IGNORED`, the file unchanged, the tab re-rendered.
  4. A stale tab (last upload moved) showing a tick the classifier has since cleared: not re-ticked.
  5. A year file changed on Drive: classified, committed, its tab uploaded, with no reprocess.
  6. The same row changed on Drive and its Category Manual on the tab: the sheet wins that cell, the Drive edit keeps the rest.
  7. Drive moved mid-run: upload `conflicted`, the base not moved; the next run merges both.
  8. The sheet moved mid-run: the tab `moved`; the next run merges it.
  9. The Classifier tab changed, then held: every file reclassified, then the last applied tab used.
  10. Redbark 429 then 200; 429 until the budget ends: `TRANSACTION_CALL`, nothing lost.
  11. Sweep: a held row 40 days old gone and relisted, a blank `Date Posted` filled, an unheld row raised, nothing added.
  12. A manual file with a name-only row: the id filled; an unknown name: the file left as is, errored, not committed.
  13. An edit on an id no file holds: `EDIT_UNMATCHED`.
  14. A name twice on Drive: `DRIVE_DUPLICATE`.
  15. A tab cut short by a failed upload: no edit.
  16. A fresh cache with no base: edits taken against the files.
  17. Reprocess: every state rebuilt, every tab uploaded, every file verified, nothing re-uploaded that matches.
  18. The tab sorted by another column with a split edited: the right parts change.
  19. The Classifier tab edited so Bucket values change on a year tab: no `TAB_EDIT_IGNORED`.
  20. A tab edit on a row whose Date Redbark adopted last run, the tab not re-rendered since: applied by Source ID.
  21. A manual file saved by Excel (BOM, CRLF, `dd/mm/yyyy`, `$1,234.00`): parsed; an ambiguous value rejected by row.
  22. A file conflicted on sync: its year's tab not uploaded, the base not moved, both merged next run.
  23. Backoff across accounts reaching the run budget: the remaining calls fail as errors, and the run finishes in time.
  24. Change log:
      - a sheet edit and a classifier tick clear are logged; a Derived-only move is not;
      - a split change is logged with `Split Before`/`Split After`;
      - a conflicted file's change is not logged, then is logged on the replay;
      - the first run after the cutover starts a new month file in the new format only.
- **Local AMEX** (synthetic exports, same scaffolding), one case each:
  1. A new `activity.csv`, two cards, one account: renamed to `amex_xxxx0001_transactions_<last>.csv`, every row added with
     `Date Posted`, amounts negated, classified, committed; card and member in no output.
  2. A second export overlapping the first by a month: only rows after the overlap added, nothing doubled.
  3. Three identical same-day charges in both exports: three rows, not six and not one.
  4. Held rows in the overlap with Category Manual, a tick, and one split in two parts: all kept exactly, `Date Posted` filled.
  5. A byte-identical re-download: renamed with `_2`, nothing added.
  6. Two exports with the same newest date: `_2` on the second.
  7. Post-rename runs: a standard run reads neither export; an export edited on Drive is read again; `--force-downloads` reads
     every one; a reprocess reads none.
  8. A row deleted from the year file: stays deleted on a standard run and a reprocess, comes back on `--force-downloads`.
  9. Mapping: by a hand-renamed name; by a card seen in an earlier renamed export, with no overlap; by overlap alone; a new card
     with no overlap left as `activity*.csv` with `IMPORT_UNMAPPED`; known cards of two accounts; overlap split between two accounts;
     a Linked account. Each case is renamed and imported, or left alone with its error.
  10. A wrong header, a bad date, three decimals: `IMPORT_UNREADABLE`, unrenamed, nothing imported.
  11. A held row inside an export's span that it does not list: `IMPORT_GONE`; a hand row two days off a new one: `IMPORT_SUSPECT`.
  12. A BOM, no final newline, runs of spaces, `dd/mm/yyyy` with day over 12, a credit: parsed.
  13. A Drive rename that fails: old name kept, error, renamed on the next run. A local rename that fails after Drive renamed:
      nothing re-uploaded, the new name downloaded next run. Two Drive files both named `activity.csv`: each renamed, both
      imported.
- **Preview**: today's refresh replay plus a tab edit and a Drive edit against the preview Drive and sheet, asserting the file
  lands on Drive and the tab is not re-uploaded. `refresh.sh` also copies release's AMEX exports, renamed or not, and the test
  renames and imports them on the preview Drive: every row parsed, none unreadable, counts per export equal to its rows, a second
  run adds nothing.
- **Release**: today's live run, asserting no conflict and no ignored edit on real data, plus the two real exports over their full
  history against the held rows:
  - each export maps to its account by overlap;
  - nothing is unreadable;
  - only rows no year file holds are added (the 3 `activity.csv` rows on the first run, none once they are held), with no held
    row's Category Manual, Vetted or split changed;
  - blank `Date Posted` values are filled;
  - a second run adds nothing.
  Uploads are off, so only the local copies are renamed.

## 11. Rollout

The work is built in the order below, but ships as **one release with a clean cut**. No compatibility code, read-side alias or
one-release overlap survives in the code, and no old-format file survives in the data.

### 11.1 Build order

1. `_sources.py` changes and their tests (sheet by content, Drive manifest, backoff, download-only names, `drive_rename`), all
   plugins.
2. Bank 3-way merge, the per-year states with whole-partition replace, and the fixed ordinal order.
3. Manual rows and balances by file: delete the sheet entry code and the placeholders outright.
4. AMEX imports: the `.gitignore` lines first, then the code.
5. Sweep.
6. Change log in the new format; `CHANGES_UNLOGGED` and its guard deleted.
7. Headers and labels in every plugin. `CLAUDE.md`'s Bank, Data flow and Personal financial data bullets rewritten, `classifier.md`
   and `hsbc.md` cut to what is still open.
8. The review in section 12, after each step and in full at the end.

### 11.2 Cutover

Done once, on release, with the service stopped so no run starts part way:

1. **Before deploying**, on the old release:
   - move any manual rows or balances still typed on the sheet into the `manual_*` files on Drive;
   - confirm the last run's `Tabs uploaded` line shows nothing `skipped moved` or `failed`, and its `Logs` tab has no
     `CLASSIFIER_HELD`. The cutover deletes the classifier snapshot, so a held tab would leave nothing to classify with.
2. **Deploy, then stop the container** before its first run. Release data is restored into the new release's directory
   (`/home/asystem/wrangle/<version>/data`; `restore.sh` carries all of `data/bank`), so the cleanup below runs there.
3. **Archive:** copy the bank Drive data folder and the new release's `data/bank` to `~/Backup/asystem/wrangle-cutover-<date>/`,
   outside Drive's data folder and the cache. This is the only place the old residue lives on, for rollback.
4. **Drop residue on Drive** (moved to Drive's trash, which keeps it 30 days): every `bank_reclassified_*` file.
5. **Remove the monthly placeholder rows** from `manual_transactions_*` on Drive, so no placeholder rule is ever written.
6. **Drop residue in the cache,** so the first run rebuilds everything in the new format:
   - `bank_reclassified_*`;
   - the old single state, `__bank_transactions_{current,previous,delta,update,deleted}.csv`, and `__bank_balances_*`;
   - every `_sheet_bank_*` file: the version caches numbered by the old Drive version, and the `_format.json` beside them;
   - `__bank_classifier.csv` and `__bank_accounts_dimension.csv`, so the first run classifies every file;
   - `__bank_logs.csv`, so the `Logs` tab carries no first-seen dates or codes from the old release.
   Year files, `manual_*`, exports and `_redbark_*` caches stay. The year files are pulled from Drive anyway.
7. **Start the container.** Its first loop run is the cutover run, with no flag needed:
   - no manifest, so it builds one from Drive;
   - no bases, so tabs are diffed against the files, which also picks up any edit the old release missed;
   - the exports are new, so they are renamed and imported;
   - no classifier snapshot, so every file is classified;
   - no states, so every year is built;
   - every tab is re-rendered, and the change log starts.
   `--force-downloads` is not exposed by the run API, and nothing in the cutover needs a full Redbark history check.
   Read its `Logs` tab: expect the 3 `activity.csv` rows added, and no `EDIT_UNMATCHED`, `DRIVE_CONFLICT` or `TAB_EDIT_IGNORED`.
   Then trigger one reprocess from the dashboard, and confirm it changes nothing. That proves the first run converged.
8. **Check the clean state:**
   - no file in the cache or the Drive data folder matches an old-format pattern;
   - `grep` of the code for every removed name and code (`CHANGES_UNLOGGED`, `TRANSACTION_PLACEHOLDER`, `_sheet_version`,
     `files_changed`, `bank_files`, `__editable`) finds nothing.

Steps 3 to 6 are a short script under the module's `src/build/resources/` (shellcheck clean), run by hand once on the host and
deleted after the release, so it is not left as residue either. Drive steps 4 and 5 use the service account the plugin already
uses.

Expected size: `bank.py` from about 2380 lines to about 1850 to 1950, the balances merge, the manual-row entry and placeholders
going and the import adding about 120; `_sources.py` about 60 lines longer.

## 12. Review

The quality gate after the build. It covers **all of `bank.py`**, not only the lines this plan changes, plus **every shared
function bank reaches**, followed through to its end:

- `_sources.py`: `sheet_download`, `sheet_upload`, `sheet_update`, `sheet_ensure`, `sheet_cached`, `drive_synchronise`,
  `drive_rename`, `redbark_download` and their private helpers;
- `_state.py`: `state_cache`;
- `_logs.py`: `error`, `logs_merged`;
- `_dataframes.py`: `csv_read`, `csv_write` and the frame helpers;
- `plugin.py`: `run`, `now`;
- `config.py` and `counters.py`, for the constants and counters bank uses.

Where a shared function changes, every other plugin that calls it (equity, currency, interest) is reviewed for that change too.
Every finding is fixed, or written down with its reason, before the work counts as done.

### 12.1 Correctness

- **Check all logic.** Walk each block of the section 4 flow against principles 1 to 5 and the column-ownership table: every column
  written only by its owner, every snapshot moving forward only after its files are on Drive.
- **Run twice.** A second standard run on the same inputs writes, uploads and syncs nothing, and its log shows only cached lines.
  Asserted in every local case that changes data.
- **Kill and resume.** Stop a run after each block (download, merge, fetch, derive, commit, upload, sync), then run again. The end
  state must equal an uninterrupted run, with no edit lost or doubled. Done by patching the first shared call of the next block (`drive_synchronise`, `sheet_upload`, `state_cache`, `csv_write`) to
  raise, so no test-only hook goes into production code.
- **Identity unchanged.** The pinned account, balance and transaction ids in the unit tests still pass with no edit. Changing one
  would be a data migration (CLAUDE.md, Bank).
- **Vocabulary both ways.** List every error code `error(...)` raises and diff it against `ERROR_CODES`, in both directions: no code
  raised but undeclared, none declared but never raised. Do the same for counters against `COUNTERS`, and for the file families
  against `FILE_NAME_PATTERN`, the `.gitignore` lines and the sync's skip rules.
- **Generated output.** `fab generate` regenerates the schema and model files byte-identical, unless a step meant to change them.

### 12.2 Simplicity and match with equity

- **Block structure.** `bank.py`'s `_run` reads as the numbered blocks of section 3, in the order and with the labels of its file
  header, the same shape as `equity.py`.
- **Style.** Naming, closure idiom, dataframe idiom, log wording and constant layout as in `equity.py`.
- **Comments.** Only the flow header, the one-line block labels, the docstrings CLAUDE.md allows (source entry points and
  `state_cache`), and a note where a process genuinely needs explaining. No other comments.
- **Dead code.** Remove code nothing reaches: the placeholder paths, `__editable`, the stale re-tick guard, the old `bank_files`
  and `files_changed` bookkeeping, the Drive version helpers, unused constants and error codes.
- **Single-use functions.** Apply the global rule: inline one-call-site helpers as local closures beside their use, or as plain lines.
  Keep a separate definition only for a pure function with a real input space (the export parser, the 3-way tab diff, the account
  mapping), each with its own table test.
- **Layout.** Organise constants, functions and closures by the project guidelines: primary code first, private helpers and
  constants at the bottom.
- **Size.** Measure `bank.py` against the section 11 estimate, and explain any overshoot.

### 12.3 Performance and Polars

- **Row loops.** Replace `iter_rows`/`to_dicts` loops with expressions wherever they handle data, not a handful of error rows: the
  per-transaction edit loop, the account fill, the Redbark match's `while` loop, the reconciliation's per-reading loop. Keep a loop
  only where it reads better and the data is small.
- **Read once.** Each year file is read once per run (the `files_read` cache), and the merge, import, classify and commit blocks
  share that frame rather than re-reading from disk.
- **Lazy frames.** Use lazy frames for the wide joins (accounts applied, held against fetched, state merge) where that measurably
  saves time.
- **Ids.** Derive transaction and balance ids from one vectorised hash pass, not a Python loop over rows per call. Then check the
  pinned ids still pass.
- **Call budget.** An idle standard run makes a fixed number of Google calls: one Drive listing, one sheet read, no uploads, no
  version lookups. A run with one edit adds only that file's upload and its tab's guard read. Asserted by counting calls in a
  local test with mocked clients.
- **Timings.** Record wall time for an idle run and a one-edit run on the release fixture, before and after. Block timings must add
  up to the total, with none nested inside another.

### 12.4 Tests

- **Coverage of scenarios.** Map every row of section 10's local list, and every transaction, balance and account scenario in today's
  suite, to a test. Add edge cases where one is missing. Run accounts, balances and transactions together in one case where they
  interact (a renamed account across both states, a manual balance carried onto linked moments, reconciliation against imported
  rows), and isolate them only where a failure would otherwise be ambiguous.
- **Value.** Remove or rewrite tests that assert log or message wording, padded numbers, or implementation shape, per the memory
  rules. Assert codes, counters, file contents and tab contents instead.
- **Bite.** For each new behaviour, plant a deliberate fault (skip the 3-way base advance, sum export rows instead of taking the
  union, upload a conflicted file) and confirm a test fails. Then revert.
- **Synthetic only.** No real merchant, amount, card, member or account number in any local fixture or test. Check with a grep
  against the release data's distinctive values, run locally and never committed.
- **Preview and release.** Run both after the local suite passes. Re-run a release failure once before believing it, since some
  tests hit live APIs.

### 12.5 Project guidelines

- Read the root, module and global `CLAUDE.md`s, and check each rule:
  - `ruff check`, `ruff format` and pyright clean through the build, with no unexplained-but-needed suppression;
  - suppression directives written bare, with no explanation beside them;
  - whole-word names, and imports at the top;
  - `[value]` brackets and no `:` or dashes in log and error messages;
  - amounts and descriptions logged only at debug or in an operator error, full account and card numbers never (masked `xxxx####` is fine);
  - every network call bounded by a timeout;
  - no runtime import of `plugin/schema.py`.
- `shellcheck` on any shell touched (`refresh.sh`, `backup.sh`).
- `git check-ignore` confirms that real exports, renamed exports and the release and preview `data/` dirs are ignored, and that
  the synthetic local fixtures are not.
- CLAUDE.md's Bank, Data flow and Personal financial data bullets match the code, name no test, and the plans that are now built
  (`classifier.md`'s parts, `hsbc.md`'s proposed changes) are cut down to what is still open.
- Every departure from this plan has a section 15 entry, and the sections it touches describe what was built.
- The working tree is left unstaged, with no git writes.

## 13. Pressure test

### 13.1 Gaps found and now folded into the plan

1. **Formula columns read as edits.** Category and Bucket change on the tab whenever the Classifier tab does, so diffing them would
   raise `TAB_EDIT_IGNORED` on every classifier edit. They are excluded (4, 3.2).
2. **Split parts keyed by row position.** A tab sorted or filtered by the operator could move a Vetted tick onto another part. Parts
   are now compared as a set per id (3.2).
3. **An id that changed under the tab.** When Redbark adopts a Date, or a Drive edit changes a description, the tab still shows the
   old id until it is re-rendered, so an edit made in between would be unmatched. Edits now fall back to Source ID, then to a
   unique account, cents and three-day match (3.2).
4. **Tabs uploaded before a Drive conflict.** Uploading tabs before the sync could show rows that then failed to reach Drive. Next
   run they would appear as edits on ids no file holds. The sync now runs first, and a year whose file conflicted is not uploaded
   (8, 9).
5. **Batch guard window.** One guard read for all tabs left seconds between the read and each write. Each tab is now re-read just
   before its own write, and only written tabs pay for it (9.2).
6. **Base storage split across modules.** Having `_sources.py` cleanup know bank's committed base version tied the two modules
   together. Bank now keeps its bases as `__bank_tab_<tab>.csv` (10.1).
7. **Backoff budget per call.** With 8 accounts this could pass the 10-minute run timeout. The budget is now shared by the whole run
   (6.3).
8. **Sweep relisting on recurring charges.** 90 days of same-amount repeats (subscriptions, daily purchases) could pair the wrong
   rows. Adoption outside the add window is now one to one only (6.4).
9. **Operator files saved by Excel or Sheets.** A BOM, CRLF, `dd/mm/yyyy` dates or `$1,234.00` must parse or be rejected by row,
   never misread (3.1).
10. **Equity's `drive_synchronise` caller** breaks on the new return type, so it moves in the same change (6.2).
11. **Review scope.** The review covers all of `bank.py` and every shared function it reaches, not only changed lines (12).

### 13.2 Migration items the rollout must carry

- **Per-year states.** The cutover removes the old single-state files, and its reprocess builds every year (11.2). The tests'
  `state=` names are updated. Nothing outside the plugin reads the state files (no server or build reference).
- **First run with no manifest or bases**, which is the cutover run, and any later cache loss: every tab is diffed against the
  files (today's behaviour), so the stale-tab protection is off for that one run. A normal release keeps them, since `restore.sh`
  carries all of `data/bank`.
- **Preview fixtures with exports.** 8 Sync never uploads exports, so the preview test's setup must place release's exports on the
  preview Drive itself (`drive_upload` in the test helpers), not rely on the run.
- **Open sheet entries** are moved into files before the deploy (11.2, step 1).

### 13.3 Residual risks, accepted

- **Write window on a tab.** Sheets has no conditional write, so an edit made in the second or so between a tab's guard read and
  its write is lost. It is far narrower than today's, where the version lag makes it minutes. Only tabs that actually change are
  written.
- **Edits on a row whose identity changes in the same run.** If a Drive edit changes a row's date or description while its
  operator column is edited on the tab, and the fallbacks find no unique match, the result is `EDIT_UNMATCHED`. The edit is
  reported, never applied to the wrong row.
- **`--force-downloads` restores deleted export rows.** A row deleted from a year file comes back when every export is re-read,
  and its `added [n]` is logged. Deleting at the source is not possible with AMEX, so this is the explicit trade.
- **A new card's first export with no overlap** needs one hand rename (7.2).
- **Hand-typed AMEX rows that differ from the export** raise `IMPORT_SUSPECT` and `IMPORT_GONE` until the operator deletes the hand
  copy on Drive.
- **Rows missed by an earlier hand import.** `activity.csv` shows 3 AMEX rows from early October that are in no year file (7.1).
  The import adds them. The general risk is a held AMEX history with gaps, which the first import fills and logs as `added [n]`.

### 13.4 Second pass: gaps found and folded in

1. **Base kept back on a `moved` upload replayed old edits.** If a tab's upload was skipped because the operator edited it mid-run,
   keeping the old base meant the next run would replay that run's edits. A Vetted tick the classifier had cleared in between would
   come back. The base now moves to the 1.2 version whenever its edits reached Drive, and stays back only on a Drive conflict
   (10.1).
2. **Text comparison of tabs.** The sheet shows `1,234.00` where the upload wrote `1234.0`. Version detection and the 3-way diff
   now compare typed values, or every upload would be followed by a spurious version and `TAB_EDIT_IGNORED` noise (3.2).
3. **Per-year states kept deleted rows.** `state_cache` only deletes keys with `replace`. Each year's state now replaces its
   partition whole, so a row deleted on Drive, by dedupe, or by a conflict rollback leaves the state (6.2).
4. **Ids could swap when a repeat is appended.** Ordinals were counted with `manual_*` before `redbark_*`, so importing a repeat
   whose twin sits in a redbark file would swap the two rows' ids. The order is now fixed with appends last, and the
   one-off re-id is counted first (7.4). This is a latent bug in today's code too.
5. **Download-only names were bank-local.** `Plugin.run`'s closing sync would have uploaded a stale `activity*.csv`. Download-only
   patterns are now a `Plugin` attribute that both syncs honour (6.2).
6. **Manifest written only at the end.** A run killed mid-sync could re-upload or misjudge files. The manifest is now written
   atomically per upload, and a file equal on both sides is always recorded (6.2).
7. **Partial last day of an export** would have raised false `IMPORT_GONE`. First and last days are excluded (7.4).
8. **Pending AMEX rows** (blank `Date Processed`) could post later with a different amount or description and then duplicate.
   They are skipped (7.4).
9. **Manual balance files had no normalise rules.** They now get the same treatment as transactions (3.1).
10. **Where exports go** was unstated. They go in the synced data folder, since the Drive sync only reads that folder (7).

### 13.5 Decisions

- **Account number in file names and logs: decided.** Only full account numbers are never logged; the `Accounts` tab's masked
  `Number` (`xxxx` and the last four digits) is fine in file names and logs. The module `CLAUDE.md` says so already, so
  `amex_xxxx1000_…` stands.
- **CLAUDE.md's "finds edits against the files by id (never a saved upload or a row position)"** is reversed on purpose. Its reason,
  that a saved upload may not be what is on the sheet once an upload is skipped, is met by the base rule in 10.1: the base is
  only ever the tab as downloaded, or as fully uploaded. The bullet is rewritten in build step 7 (11.1).

### 13.6 Residual, accepted

- **A kill between 8 Sync and 9 Upload in the same run as a classifier move on an operator-ticked row.** The next run can replay
  the tick. Writing each base straight after its tab's upload keeps the window to that one gap.
- **New error codes need their kind and standing in `ERROR_CODES`.** `IMPORT_UNMAPPED` and `IMPORT_UNREADABLE` are standing errors
  (they hold until the file is fixed). `IMPORT_GONE`, `IMPORT_SUSPECT` and `TRANSACTION_UNHELD` are standing warnings.
  `TAB_EDIT_IGNORED`, `EDIT_UNMATCHED`, `DRIVE_CONFLICT` and `DRIVE_DUPLICATE` are per-run errors. The vocabulary check in 12.1
  enforces both directions.

### 13.7 Third pass: gaps found and folded in

1. **An invalid manual file dropped its rows from the state.** With whole-partition replace, committing a year without its
   rejected file would delete that file's rows. The whole year is now left as committed (3.1).
2. **Sweep retried on every run after a failure.** Its due date came from a cache written only on success. It is now stamped on
   attempt (6.4).
3. **Test-only hook in production.** Kill-and-resume now patches the next block's first shared call instead (12.1).
4. **Blue cells promised edits the sheet no longer takes.** Highlights and dropdowns now follow the new editability (9.2).
5. **The cutover could not run as written.**
   - `--force-downloads` is not on the run API, and the service's first loop run would race the cleanup.
   - The container is now stopped across the cleanup, and the first loop run is the cutover run, which needs no flag.
   - A follow-up reprocess must change nothing (11.2).
6. **The cutover left residue.** `__bank_logs.csv` and the `_format.json` files are now dropped too.
7. **Cutover preconditions.** A held Classifier tab, or a tab whose last upload was skipped, would make the first run lose a held
   edit or take a stale tick. Both are checked before deploying (11.2, step 1).

## 14. Implementation handoff

For a fresh session picking this up.

- **Status.** This plan is agreed; nothing is built. Start at build step 1 (11.1) and run the review (12) after each step.
- **Read first:**
  - the root, module and global `CLAUDE.md`s;
  - this plan;
  - `classifier.md` and `hsbc.md` beside it;
  - `bank.py` whole;
  - in `_sources.py`: `sheet_download`, `sheet_upload`, `_sheet_moved`, `drive_synchronise`, `redbark_download`;
  - `_state.py`, and `equity.py` for style.
- **Code anchors** (as of this plan):
  - `bank.py:1080` (sheet merge gate) and `bank.py:1198` (silent unmatched edit);
  - `bank.py:1739` (classify set) and `bank.py:1947` (manual-first ordinal order);
  - `bank.py:1846` (`bank_files` bookkeeping);
  - `_sources.py:669` (Drive version lookup) and `_sources.py:1397` (`_sheet_moved`);
  - `_sources.py:1206` (`drive_synchronise`), `_sources.py:222` (Redbark errors), `equity.py:366` (sync caller).
- **Tools:** `~/.pyenv/versions/asystem/bin/{python,pytest,ruff}`. Run tests from `src/test/python/unit` with `pytest unit_test.py -k
  <name>`, scoped to the cases touched; the full suite only before release. `fab build` in the module lints, formats and type
  checks, and rewrites source, so read the diff after.
- **Release, read-only:**
  - `ssh root@macmini-mad`;
  - `docker logs wrangle` for runs;
  - data in `/home/asystem/wrangle/<version>/data/bank`.
  Print counts and shapes only, never values: personal financial data never leaves the host, and never enters git, a fixture, a
  test or a doc.
- **Rules that bite here:**
  - no git writes;
  - synthetic local fixtures only;
  - no test asserts log wording;
  - one-call-site helpers inlined;
  - `[value]` log style;
  - no comments beyond the flow header and block labels;
  - `.gitignore` lines before any export fixture.
- **Record deviations here.** When the build departs from this plan (a design changed, a step reordered, a test dropped or added,
  a gap found while building), add an entry to section 15 in the same change, before moving on. Then update the section the
  deviation touches, so the plan always describes what is built. Never leave a section saying one thing while the code does
  another.

## 15. Implementation deviations

One entry per deviation, newest last. Each entry gives:

- **Where:** the plan section and build step.
- **Planned:** what the plan said.
- **Built:** what was done instead.
- **Why:** the reason, such as a fact found in the code or data, or a simpler route.
- **Effect:** the tests, cutover steps or other sections it changes, and that those were updated.

No values from personal data, as everywhere in this plan. When the build is done, section 12's review checks that every
deviation is reflected in the sections it touches, and the entries stay as the record of how the build differed.

None yet.
