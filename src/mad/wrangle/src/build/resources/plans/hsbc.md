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
  readings reconciled against held rows (`BALANCE_UNRECONCILED`, about a week behind).
- Drive, 19 Oct 2026: the 7 dropped rows on the Oct statement re-dated to their statement day with `Date Posted` 2026-10-12; the
  2 never-listed charges added without a Source ID; `Date Posted` filled from Redbark wherever it lists a row.

## Blank `Date Posted`

Blank means no Redbark row has dated it; never fill it with `Date`. The code dates a blank row only when Redbark lists it by its
Source ID, or matches an id-less one inside the recent fetch window. The 181 gap rows and 2 added charges are outside that window,
so if Redbark re-syncs nothing happens automatically: match each blank, id-less row one to one to an unheld Redbark row by account,
cents and purchase day (Sydney day of `datetime` for HSBC), then set `Date Posted` and adopt the Source ID. A dropped row relisted
after the window has passed is likewise not noticed. The 8th dropped row (posted 13 Oct) still has `Date` on its posting day and
`Date Posted` blank until the Nov statement gives its purchase day.

## Next

1. Ask Redbark support whether Fiskil's raw HSBC feed holds a missing transaction (say a Saturday purchase in May), to place the
   fault in HSBC, Fiskil or Redbark, and whether the history can be re-synced. Cite the lag pattern and the October drops.
2. If Redbark re-syncs, run the matching backfill above, dry run first.
3. Nov 2026 statement (13 Oct to 12 Nov): set the 8th dropped row's dates and reconcile every line, adding any missing by hand on
   Drive between runs.
4. Reconcile each later statement until Redbark is reliable, or build statement reconciliation into bank.

## How to check a statement

- `pdftotext -layout`; lines are `dd/mm/yy[yy] [card] description $amount` (credits `-$`) plus undated fee lines of the previous
  date; opening minus the signed sum must equal closing.
- Compare with the Sydney day of Redbark's `datetime`, not its Perth `date`; match by account and cents to the nearest day, one to
  one.
- Redbark from the host: `docker exec wrangle python3 -c …` against
  `https://api.redbark.com/v1/transactions?connectionId=…&accountId=…&from=…&limit=200&offset=…` with
  `Authorization: Bearer $REDBARK_TOKEN`; ids in `data/bank/_redbark_accounts.csv`.
