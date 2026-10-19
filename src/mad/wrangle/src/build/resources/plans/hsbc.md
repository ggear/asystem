# HSBC transactions missing from Redbark

No merchant, amount or id appears here; see the `Logs` tab, the statements (`Wrangle/Bank/archive/transactions/pdf`) and the year
files (`Wrangle/Bank/release/data`) on Drive.

## Findings

- **191 HSBC Credit transactions are not in Redbark**, all on HSBC's statements: 181 from Apr to Sep 2026 (about a third of each
  month, both cards), 8 listed in October then removed (`TRANSACTION_GONE`), and 2 in October never listed. Before Apr 2026
  Redbark's HSBC history is complete. None is lost from the year files (statement imports, kept rows, 2 added by hand).
- **Cause: posting lag.** From April, Redbark loses most transactions HSBC posts 2 or more days after purchase. HSBC posts on
  weekdays only, so Friday and Saturday purchases (posted Monday) are missed 61% and 72% of the time, other days about 20%. Card,
  merchant, amount and description play no part, and there is no daily cap.
- **HSBC only.** Bankwest (which also posts late at times) and CBA are complete against Redbark.
- **Where.** Redbark takes all accounts from Fiskil, a CDR intermediary; its v2 API (header `Redbark-Version: 2026-10-01.wattle`)
  returns the same gap as v1. So the loss is in HSBC's CDR feed, Fiskil, or Redbark's import. A guess: a pending transaction
  reconciled with its posted copy only within about a day.

## Done

- Code (10.200.1837): dropped rows kept and flagged (`TRANSACTION_GONE`), relisted ids adopted (`TRANSACTION_RELISTED`), balance
  readings reconciled against held rows (`BALANCE_UNRECONCILED`).
- Drive, 19 Oct 2026, each written between runs with a backup and checked to change only the intended cells:
  - the 7 dropped rows on the Oct statement re-dated to their statement day, `Date Posted` 2026-10-12; the 8th dated from the
    19 Oct export (purchase 10 Oct, posted 13 Oct); the 2 never-listed charges added without a Source ID;
  - `Date Posted` filled from Redbark wherever it lists a row, from HSBC date-range exports and AMEX activity exports
    (`archive/transactions/csv`), repeat same-day purchases included;
  - Bankwest history re-dated to purchase day and given its Redbark Source IDs, CBA history given its Redbark Source IDs;
  - 2 AMEX purchases from 16 and 17 Oct added from the AMEX activity export.
- Rows added or changed on Drive by hand are rebuilt into the sheets but not classified, so a reprocess run follows any hand edit.

## Blank `Date Posted`

Blank means no Redbark row has dated it; never fill it with `Date`. The code dates a blank row only when Redbark lists it by its
Source ID, or matches an id-less one inside the recent fetch window. The 181 gap rows and 2 added charges are outside that window,
so if Redbark re-syncs nothing happens automatically: match each blank, id-less row one to one to an unheld Redbark row by account,
cents and purchase day (Sydney day of `datetime` for HSBC), then set `Date Posted` and adopt the Source ID. A dropped row relisted
after the window has passed is likewise not noticed. HSBC's online banking exports only the last 90 days, so the gap rows from
Apr to mid Jul 2026 and the 2021 to 2023 history stay blank for good; that is correct, not a fault.

## Next

1. Ask Redbark support whether Fiskil's raw HSBC feed holds a missing transaction (say a Saturday purchase in May), to place the
   fault in HSBC, Fiskil or Redbark, and whether the history can be re-synced. Cite the lag pattern and the October drops.
2. If Redbark re-syncs, run the matching backfill above, dry run first.
3. Monthly, export HSBC's last 90 days and AMEX's activity as CSV into `archive/transactions/csv` (`HSBC_xxxx0651_<download
   day>.csv`, `American Express_xxxx<card>_<download day>.csv`), then match them to the held rows: add any missing transaction,
   fill blank `Date Posted`, and reprocess. This finds drops weeks before the statement. Reconcile each statement too.

## Proposed code changes

Not built; each removes a manual step above.

- **Import bank exports:** match a CSV dropped in `archive/transactions/csv` (HSBC 90-day, AMEX activity) to the held rows on
  each run: add transactions no feed has, fill blank `Date Posted`, and log export lines with no held row and held rows missing
  from an export covering their dates.
- **Weekly 90-day sweep:** fetch the last 90 days once a week and only check (gone, relisted, `Date Posted`), never add rows, so
  drops and relistings older than the two-week window are seen. About 8 calls a week; back off and retry on Redbark's 429.
- **Drive upload conflict:** re-list Drive before uploading and skip a file that moved since the run started, with an error, so
  an edit saved mid-run is not overwritten.
- **Classify files changed on Drive**, so a hand edit needs no reprocess.
- **Check CBA dates** against a CBA statement or export: CBA is a Sydney bank, so it may need Sydney-day dating like HSBC.

## Editing the year files by hand

Edit the Drive copy (`Wrangle/Bank/release/data`) between server runs: the last run's time is the latest `Upload complete` in
`docker logs wrangle` on the host, and runs come about every 30 minutes. Read the file back as CSV and write it byte for byte,
changing only the intended cells; a re-dated row needs its Transaction ID re-derived (`bank_transactions_identified`). Confirm
Drive's md5 matches before the next run, then reprocess. Roll back from the file's Drive version history.

## Moving day-to-day spending off HSBC

BWA Joint is the safest home: Redbark's Bankwest feed is complete, late postings included, and it is already linked and
classified. A new card (Bankwest or CBA) is untested on Redbark, and the HSBC fault is on a card, so reconcile its first one or
two statements against the year files before trusting the feed; a CBA card may also need Sydney-day dating.

## Watch, from 20 Oct 2026

What to test, what to expect, and how to read a wrong answer. Read the `Logs` tab after the runs of each day that week.

- **The 6 HSBC purchases made Thu 15 to Sun 18 Oct and posted Mon 19 Oct**, the slow-posting kind Redbark loses. Expect them
  fetched by the first run of 20 Oct. A `TRANSACTION_GONE` for any in the following days confirms the fault live: check it against
  a fresh 90-day HSBC export, keep the row, and add it to the Redbark support case. If none goes, the fault may be confined to
  history, which is worth telling Redbark too.
- **`BALANCE_UNRECONCILED` from about 22 Oct**, when the first Redbark balance readings (from 15 Oct) are a week old and judged.
  Expect none for Bankwest and CBA, which backtested clean since 2025. On HSBC, expect one only where a transaction went missing
  (its amount, about a week later), and none for the 8 dropped rows, which are held. Each entry names two readings and the amount
  the balance moved beyond the held transactions: negative is a charge missing from the files, positive a held charge the bank
  reversed.
  - **Check one** against the bank's export for the days between its two readings: a missing line of that amount is a true
    positive, so add it by hand and reprocess; the error clears on the next run.
  - **False positive, likely causes:** Redbark listing a transaction more than a week after the balance moved (raise
    `BALANCES_RECONCILE_SETTLE_DAYS`); a pre-authorisation held in the balance for over a week then released (a break and its
    reversal, a few days apart, same amount); more than 12 transactions in flight on one day, where the check falls back to all or
    none (`BALANCES_RECONCILE_IN_FLIGHT`). Nothing acknowledges an entry: it stands until its readings pass the 35-day window or the
    data is fixed, so fix the data or tune the constant rather than ignore it.
  - **False negative, possible causes:** a missing amount matched by chance by a subset of that day's in-flight transactions; a
    missing and a spurious transaction cancelling out; a drop older than the 35-day window or before an account's first reading;
    accounts with no linked balance (AMEX) are never checked. The monthly export reconciliation is the backstop.
- **`TRANSACTION_GONE` false positive:** a row Redbark legitimately revised under a new id is relisted, not gone; if a `GONE`
  is followed by a matching `TRANSACTION_RELISTED`, nothing is lost. A row with no `Date Posted` is judged by its date less 7 days,
  so one near the window edge may be flagged early.
- **`TRANSACTION_RELISTED` false positive:** a genuinely new purchase of the same amount on the same account within 3 days of a
  dropped row takes its place, and one transaction is lost. Expect `BALANCE_UNRECONCILED` for that amount a week later, or catch it
  in the monthly export match; add the lost one by hand.

## How to check a statement

- `pdftotext -layout`; lines are `dd/mm/yy[yy] [card] description $amount` (credits `-$`) plus undated fee lines of the previous
  date; opening minus the signed sum must equal closing.
- Compare with the Sydney day of Redbark's `datetime`, not its Perth `date`; match by account and cents to the nearest day, one to
  one.
- Redbark from the host: `docker exec wrangle python3 -c …` against
  `https://api.redbark.com/v1/transactions?connectionId=…&accountId=…&from=…&limit=200&offset=…` with
  `Authorization: Bearer $REDBARK_TOKEN`; ids in `data/bank/_redbark_accounts.csv`.
