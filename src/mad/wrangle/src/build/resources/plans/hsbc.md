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

- **Missing from Redbark's history.** Redbark's HSBC history (from 27 Mar 2024) lists every statement line to Mar 2026, then about
  a third fewer: 181 statement lines from Apr to Sep 2026 have no Redbark row, on both cards (`0651` and `9613`), 22 to 44 a month.
  The year files hold them only because those months were imported from statements, as rows without a Source ID; so a Redbark
  history sync was incomplete, and the October drops look like the tail of the same fault. Since live tracking began in October,
  Redbark lists every line but the 2 above.

- **The link is the weekend.** The 7 dated dropped rows were all made Thursday to Saturday (8 to 10 Oct) and posted together on
  Monday 12 Oct, 2 to 4 days later; rows made those days that posted on a weekday survived, as did that Monday's Sunday and Monday
  purchases, and two of its four Saturday ones. Across Apr to Sep 2026, Redbark misses 69% of HSBC purchases made on a Friday and
  76% of those made on a Saturday, against 19% to 25% on other days; credits are missed less (14%), and the week of the month makes
  no difference.
- **The cause is the posting lag.** HSBC posts only on weekdays. Of the transactions Redbark holds, those posted 2 or more days
  after purchase were 24% to 65% of each month to Mar 2026 (about 40% typically), and 2% to 22% from May (about 10%): from April,
  Redbark loses most transactions that take 2 or more days to post, which is about the third missing. It explains the rest:
  Friday and Saturday purchases post Monday, 2 to 3 days on, and go (Saturday purchase days are wholly missing on 15 of 21);
  Sunday's post Monday a day on and stay; weekday losses are partial, the occasional slow posting. The 7 dated October drops all
  posted 2 to 4 days on, and were listed then removed, so Redbark deletes them rather than never seeing them. Card, merchant,
  amount and description play no part, and there is no daily cap (the busiest day falls from 13 to 9 with no ceiling).
- **Likely mechanism, unconfirmed.** Redbark reconciling a pending transaction with its posted copy within about a day, so one
  posted 2 or more days later is left unmatched and later removed. Put the lag pattern to Redbark support, with the October drops
  as examples of a listed row removed.

In all, Redbark lacks 191 HSBC transactions: 8 dropped, 2 never listed and 181 missing from its history. They are told apart
only by what wrangle could see, since it was not fetching live before October, so the 181 may equally have been listed then
dropped; the shared posting-lag pattern makes them one fault. None is lost from the year files: the 181 came from statement imports,
the 2 were added by hand, and the 8 were kept when Redbark dropped them.

Every other line of the 86 HSBC statements since May 2021 matches a held row, and every held row in a statement period is on one.

## Done

- Drive `redbark_transactions_2026.csv`, edited 19 Oct 2026 19:08 AWST (a Drive revision exists from before): the 7 dropped rows
  re-dated from posting to their statement date, and the 2 never-listed charges added without a Source ID.
- Code (released 10.200.1837): dropped rows are kept and raised as `TRANSACTION_GONE` with the window start; a copy relisted
  under a new id is adopted (`TRANSACTION_RELISTED`); balance readings reconcile against held rows (`BALANCE_UNRECONCILED`),
  catching a future drop about a week after it.
- Year files backfilled 19 Oct 2026 20:28 and 20:53 AWST from a full Redbark fetch: every row Redbark lists by its Source ID has
  `Date Posted` (the 7 dropped rows took the posting day), and id-less CBA history matched to Redbark adopted its ids.

## Blank `Date Posted` marks a row Redbark has not dated

The 181 gap rows, the 2 never-listed charges and pre-Redbark history keep `Date Posted` blank, deliberately: blank means no
Redbark row has dated it, and filling it with `Date` would invent a posting day (HSBC posts 0 to 6 days after purchase).

The code dates a blank row automatically only when Redbark lists it by the Source ID it is held under, or, for a row without one,
when Redbark lists a match (account, cents, three days) inside the normal fetch window. The gap rows are far older than that
window, so if Redbark re-syncs and lists them, nothing happens automatically: no duplicate is added and nothing is adopted. They
need the manual matching backfill used for CBA: match each blank, id-less row one to one to an unheld Redbark row by account,
cents and purchase date (the Sydney day of `datetime` for HSBC), then set `Date Posted` and adopt the Source ID. Blank is what
selects them.

The 8 dropped rows keep their Redbark Source IDs, and blank matters differently for them:

- **The 7 on the Oct statement** are dated: `Date` is the statement's purchase day and `Date Posted` the posting day Redbark gave
  before it dropped them. If Redbark relists one under the same id it is matched by id and its dates stay; under a new id, while
  it is still inside the fetch window, it is adopted (`TRANSACTION_RELISTED`) and its dates stay. Once the window has passed it
  (late October 2026), Redbark is no longer asked for it, so a relisting goes unnoticed; check by hand as for the gap rows.
- **The 8th, posted 13 Oct**, has `Date Posted` blank and `Date` still on its posting day, because its statement had not been
  issued. When the Nov 2026 statement arrives, set `Date` to its purchase day there and `Date Posted` to 2026-10-13, by hand on
  Drive between runs. Until then it is one row dated by posting, and its gone check uses the posting fallback.

## Next

1. Raise the dropped and never-listed rows with Redbark support, with the Source IDs from the `Logs` tab: Redbark's HSBC history
   omits about a third of Apr to Sep 2026 on both cards, and 8 listed rows vanished in October. Ask whether the connection's
   history sync failed and can be re-run, then re-check its coverage against the statements.
2. If Redbark re-syncs, run the matching backfill above for the blank, id-less HSBC rows, dry run first.
3. On the Nov 2026 HSBC statement (13 Oct to 12 Nov): check the 8th dropped row is on it and set its dates as above, and
   reconcile every line against the held rows, adding any missing one by hand as above.
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
