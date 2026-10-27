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
- **Still live.** Of the 6 purchases made Thu 15 to Sun 18 Oct and posted Mon 19 Oct, all 6 were listed on 20 Oct, and 4 (Thu to
  Sat) were removed by 25 Oct: the October drop pattern, listed then removed, not the April to September one, never listed. The
  balance confirms all 4 (each breaks the reconcile when taken out), so they are held and kept. The 7 purchases of Fri 23 to Sun 25
  Oct, posted Mon 26 Oct, were listed a day late, after the balance had already moved; they match the balance exactly.
- **Weekdays too.** 4 more were listed then removed by 27 Oct: purchases made Mon 19 and Tue 20 Oct and posted Wed 21 and Thu 22
  Oct, one of them a refund and one an overseas fee. They are held, and the balance judges them from about 29 Oct. So the fault is
  not limited to Friday and Saturday purchases: a posting 2 or more days after purchase is enough, whatever the day.
- **HSBC only.** Bankwest (which also posts late at times) and CBA are complete against Redbark: on 27 Oct their whole Redbark
  history (from Dec 2019) was diffed against the year files, and every row from May 2021, where the held history starts, is held
  with Redbark's amount, `Date` and `Date Posted`. 47 rows from 2022 to 2026 are held without a Source ID or under one Redbark
  reissued, each paired one to one with a Redbark row; one Bankwest row was removed for a fetch and listed again a run later.
- **Where.** Redbark takes all accounts from Fiskil, a CDR intermediary; its v2 API (header `Redbark-Version: 2026-10-01.wattle`)
  returns the same gap as v1. So the loss is in HSBC's CDR feed, Fiskil, or Redbark's import. A guess: a pending transaction
  reconciled with its posted copy only within about a day.
- **Known CDR gaps that fit (Oct 2026).** No public report of Fiskil or Redbark losing late postings was found, but the standard
  leaves two openings. Its transactions `oldest-time` filters on an "effective time" it never defines for a transaction, so a bank
  may filter on purchase day: an incremental fetch then misses anything posted after its cursor passed the purchase day, which
  matches the lag and weekend pattern. And it guarantees no id linking a pending copy to its posted one, with at least one bank
  sending card authorisations as `POSTED` (standards-maintenance issue 656, open), so de-duplication can drop a copy, which fits
  the October drops better than the never-listed rows. Redbark syncs only posted transactions and the provider takes one refresh
  per person per 24 hours. Both point at the bank's feed rather than Fiskil.

## Done

- Code (10.200.1837): dropped rows kept and flagged (`TRANSACTION_GONE`), relisted ids adopted (`TRANSACTION_RELISTED`), balance
  readings reconciled against held rows (`BALANCE_UNRECONCILED`).
- Code (27 Oct 2026): a held row dated the first day of the check window is no longer checked for `TRANSACTION_GONE`, since Redbark
  filters `from` on its Perth `date` and an HSBC row held on its Sydney day can fall the day before (a midnight-stamped payment was
  raised gone on 23 Oct); and `BALANCE_UNRECONCILED` names the amount assuming the fewest transactions in flight, not the smallest
  gap any combination of them leaves, which reported a near-zero amount for every live drop; and transactions are fetched with
  every balance read, three-hourly, not only when a balance moved or on the day's first read: Redbark can list a transaction hours
  after the balance it moved, which then waited for the next day's fetch (the 23 to 25 Oct purchases, 27 Oct). Reads hit Redbark's
  store, not the bank, so more of them cannot worsen the feed, and they hold a row Redbark lists only briefly.
- Drive, 19 Oct 2026, each written between runs with a backup and checked to change only the intended cells:
  - the 7 dropped rows on the Oct statement re-dated to their statement day, `Date Posted` 2026-10-12; the 8th dated from the
    19 Oct export (purchase 10 Oct, posted 13 Oct); the 2 never-listed charges added without a Source ID;
  - `Date Posted` filled from Redbark wherever it lists a row, from HSBC date-range exports and AMEX activity exports
    (`archive/transactions/csv`), repeat same-day purchases included;
  - Bankwest history re-dated to purchase day and given its Redbark Source IDs, CBA history given its Redbark Source IDs;
  - 2 AMEX purchases from 16 and 17 Oct added from the AMEX activity export.

## Blank `Date Posted`

Blank means no Redbark row has dated it; never fill it with `Date`. The code dates a blank row only when Redbark lists it by its
Source ID, or matches an id-less one inside the recent fetch window. The 181 gap rows and 2 added charges are outside that window,
so if Redbark re-syncs nothing happens automatically: match each blank, id-less row one to one to an unheld Redbark row by account,
cents and purchase day (Sydney day of `datetime` for HSBC), then set `Date Posted` and adopt the Source ID. A dropped row relisted
after the window has passed is likewise not noticed. HSBC's online banking exports only the last 90 days, so the gap rows from
Apr to mid Jul 2026 and the 2021 to 2023 history stay blank for good; that is correct, not a fault.

## Next

1. Ask Redbark support whether Fiskil's raw HSBC feed holds a missing transaction (say a Saturday purchase in May), to place the
   fault in HSBC, Fiskil or Redbark, and whether the history can be re-synced. Cite the lag pattern and the 16 October drops (the
   8 of 8 to 10 Oct, the 4 of 15 to 17 Oct and the 4 of 19 to 20 Oct, listed then removed), weekday purchases among them. Ask
   whether HSBC's `oldest-time` filters on posting or execution time, and how far back each incremental fetch overlaps.
2. If Redbark re-syncs, run the matching backfill above, dry run first.
3. Monthly, drop AMEX's activity export into the bank's Drive data folder, where the run imports it, and export HSBC's last
   90 days into `archive/transactions/csv` (`HSBC_xxxx0651_<download day>.csv`) and match it to the held rows by hand: add any
   missing transaction and fill blank `Date Posted` on Drive. This finds drops weeks before the statement. Reconcile each
   statement too.

## Proposed code changes

The export import, the weekly 90-day sweep, the Drive upload conflict check and classifying Drive edits are built. Still open:

- **Check CBA dates** against a CBA statement or export: CBA is a Sydney bank, so it may need Sydney-day dating like HSBC.
- **Import HSBC exports** the way AMEX's are, once an HSBC 90-day export's format is pinned.
- **Grade `TRANSACTION_GONE` by the balance**, below.

### `TRANSACTION_GONE` today

A one-off event (not standing), so on the `Logs` tab it is `Current` only in the run that raised it, then `Historic`, an error
shown as a warning, and dropped 30 days after its `Date Raised`. It is raised only by a run that fetches transactions (every balance
read, three-hourly), for a held Redbark row Redbark no longer lists inside the check window: 14 days
behind the newest held row, 90 on the weekly sweep, the window's first day excluded. So a row that stays gone is re-raised each fetch until it leaves the window,
then weekly for about 90 days, and its detail names the window start, so each new window start is a separate entry. Two faults
follow: a row still gone reads `Historic` between fetches, and the entries multiply.

### Proposed: graded by the balance, and standing

Make `TRANSACTION_GONE` a standing problem, raised every run while true, its kind set by the balance reconcile:

- **Gone set.** Each fetch records the held rows it found unlisted (by Source ID) in a state file, and removes one Redbark lists
  again, relisted or under its own id, or the files no longer hold. Every run raises one entry per row in the set, keyed by Source
  ID, with a stable detail (no window start), so it never multiplies and its `State` means "still gone".
- **Graded against the reading pair spanning the row's posting day** (`Date Posted`, else `Date`), on linked accounts only:
  - *Confirmed*, the pair reconciles counting the row and not without it: the bank holds it and Redbark dropped it. **Warning.**
  - *Contradicted*, the pair reconciles only without it: the bank likely reversed it. **Error**: check the statement and remove
    the row on Drive if it agrees.
  - *Unjudged*, no settled pair spans it (before the account's first reading, readings under 7 days old, older than the 35-day
    window, no linked balance such as AMEX) or it reconciles either way (in-flight ambiguity): **Error**, until judged.
- **Operator acknowledgement.** A gone row ticked `Vetted` (checked against the statement) is a **Warning** whatever its grade, so
  the 8 October drops, all posted before the first Redbark reading (15 Oct) and never judgeable, stop being errors once ticked.
- **Leaving.** A row stops being raised once Redbark lists it, it is removed, or it is a warning and past both the check window
  and the 35-day reconcile window; it is then `Historic` for 30 days. An error stays `Current` until fixed or vetted.

### Proposed: `BALANCE_UNRECONCILED` in the same structure

- Stays a standing **Error**, `Current` while the break stands among the judged readings (7 to 35 days old), one entry per
  account and reading day.
- Its detail names any gone row of that account whose amount the break matches, and the gone row is then *contradicted* (break
  the opposite sign of the row) or *confirmed* (break disappears when it is counted), so the two entries explain each other.
- A break and an equal, opposite break on the same account a few days apart are a pre-authorisation held and released: both a
  **Warning**, not an error.
- A break whose readings pass the 35-day window unfixed is no longer raised, so it turns `Historic`, a warning, for 30 days from
  its `Date Raised` rather than vanishing: built, as the general `Logs` rule (any problem a run no longer raises, standing or not,
  so a fixed one lingers as a warning too).

## Editing the year files by hand

Edit the Drive copy (`Wrangle/Bank/release/data`) between server runs: the last run's time is the latest `Upload complete` in
`docker logs wrangle` on the host, and runs come about every 30 minutes. Read the file back as CSV and write it byte for byte,
changing only the intended cells. The next run takes the change by its MD5 and classifies and commits it, no reprocess needed;
an edit landing mid-run is a `DRIVE_CONFLICT`, Drive's copy winning next run. Roll back from the file's Drive version history.

## Moving day-to-day spending off HSBC

BWA Joint is the safest home: Redbark's Bankwest feed is complete, late postings included, and it is already linked and
classified. That record is thin, though: a handful of Redbark rows a year, nearly all online transfers, so the card path that
fails on HSBC (pending, then posted days later) is untested on Bankwest. Reconcile the first one or two BWA Joint statements once a
debit card carries the spending, Friday and Saturday purchases especially; its linked balance means `BALANCE_UNRECONCILED` covers
it too. A new card (Bankwest or CBA) is untested on Redbark, and the HSBC fault is on a card, so reconcile its first one or
two statements against the year files before trusting the feed; a CBA card may also need Sydney-day dating.

## Watch, from 20 Oct 2026

What to test, what to expect, and how to read a wrong answer. Read the `Logs` tab after the runs of each day.

Checked 27 Oct: the fault is live (4 of the 6 purchases posted 19 Oct went, see Findings), each a `TRANSACTION_GONE` on every
fetch since, alongside the 8 known October drops, as expected until the proposed change lands. No `BALANCE_UNRECONCILED` was
raised, correctly: every judged reading (15 to 20 Oct) on all 8 linked accounts reconciles, HSBC only because the dropped rows are
held, and taking out any one of them raises it with its exact amount. All 16 October drops belong in the Redbark support case,
the 4 weekday ones of 19 and 20 Oct (found 27 Oct) with the 12 before them.

- **Each fetch's `TRANSACTION_GONE`**: check a new one against a fresh 90-day HSBC export, keep the row, and add it to the support
  case. A Bankwest or CBA one that clears on the next fetch is Redbark flickering, not a drop.
- **`BALANCE_UNRECONCILED`**, judged once its later reading is a week old. Expect none for Bankwest and CBA. On HSBC, expect one
  only where a transaction went missing (its amount, about a week later). A weekend's purchases can be listed a day after the
  balance moved, so a break between readings under a week old is not yet a loss: on 27 Oct the balance stood ahead of the held
  rows by the 23 to 25 Oct purchases, which Redbark listed that day. Each entry names two readings and the amount the balance moved
  beyond the held transactions, assuming the fewest in flight: negative is a charge missing from the files, positive a held charge
  the bank reversed.
  - **Check one** against the bank's export for the days between its two readings: a missing line of that amount is a true
    positive, so add it by hand on Drive; the error clears on the next run.
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
  so one near the window edge may be flagged early. A gone row that is listed again under its own id on the next fetch, with no
  `RELISTED`, was a transient omission by Redbark.
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
