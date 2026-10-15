#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a due check with a moved balance appends one reading timed by its observed time and sweeps the transactions, an account with nothing held and a blank from date asking for the last seven years: postings land in the year files of their dates and one older than seven years is not fetched
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2026-01-15T09:00:00"\n"_redbark_transactions.csv" = "2026-01-15T09:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
