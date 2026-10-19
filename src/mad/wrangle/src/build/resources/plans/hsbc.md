# HSBC transactions missing from Redbark

No merchant, amount or id appears here: those live on the `Logs` tab, the statements
(`Wrangle/Bank/archive/transactions/pdf`) and the year files (`Wrangle/Bank/release/data`) on Drive.

## What is missing

The HSBC card (`HSBC Credit`, Redbark account `xxxx5418`, card `xxxx0651`) loses transactions in Redbark, all from early October
2026, around when Redbark started serving the card:

- **Dropped after listing.** 8 rows posted 12 to 13 Oct 2026 were fetched, then stopped being listed (`TRANSACTION_GONE` from 16 Oct).
  A live query from 20 Sep, wider than the fetch window, still omits them, with no replacement id and no pending row, so it is not
  the window. 7 are on the Oct 2026 statement (`HSBC_xxxx0651_2026-10.pdf`), so they are real charges inside HSBC's balance; the 8th
  posted after that statement closed.
- **Never listed.** 2 charges from early Oct 2026 are on the Oct statement but Redbark has never listed them. The gone check only
  sees rows it holds, and balance reconciliation cannot reach them (the card's first Redbark balance reading is 15 Oct), so only a
  statement shows them.

Every other line of the 86 HSBC statements since May 2021 matches a held row, and every held row in a statement period is on one.

## Done

- Drive `redbark_transactions_2026.csv`, edited 19 Oct 2026 19:08 AWST (a Drive revision exists from before): the 7 dropped rows
  re-dated from posting to their statement date, and the 2 never-listed charges added without a Source ID, so a later Redbark
  listing is adopted rather than duplicated. The server picked it up on its next run.
- Code (uncommitted at the time of writing): dropped rows are kept and raised as `TRANSACTION_GONE` with the window start; a copy
  relisted under a new id is adopted (`TRANSACTION_RELISTED`); balance readings reconcile against held rows
  (`BALANCE_UNRECONCILED`), catching a future drop about a week after it.

## Next

1. After deploying the code, set `Date Posted` to the posting day on the 7 dropped rows. The running release strips unknown
   columns, so it could not be done before, and Redbark will never list them, so nothing else will.
2. Raise the dropped and never-listed rows with Redbark support, with the Source IDs from the `Logs` tab, and ask whether early
   October was a re-sync of the HSBC connection.
3. On the Nov 2026 HSBC statement (13 Oct to 12 Nov): check the 8th dropped row is on it, and reconcile every line against the
   held rows, adding any missing one by hand as above.
4. Reconcile each later HSBC statement the same way until Redbark is shown to be reliable, or build it into bank: parse the
   statement PDFs, match each line by account, cents and date within a few days, and log lines with no held row and held rows on
   no statement.

## How to check a statement

- `pdftotext -layout` the PDF. Lines are `dd/mm/yy[yy] [card] description $amount` (credits `-$`), plus undated fee lines belonging
  to the previous date. A balance owed rises with a charge, so opening minus the signed sum must equal closing, proving the parse.
- HSBC dates by Sydney time: compare with the Sydney day of Redbark's `datetime`, not its Perth `date`.
- Match by account and cents to the nearest held date within a few days, one to one.
- Redbark itself: from the host, `docker exec wrangle python3 -c …` against
  `https://api.redbark.com/v1/transactions?connectionId=…&accountId=…&from=…` with `Authorization: Bearer $REDBARK_TOKEN`, paging
  `limit=200&offset=…`; ids from `data/bank/_redbark_accounts.csv`.
