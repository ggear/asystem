#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the first check of a new month appends its opening snapshot of every linked account to the year file though no balance moved, requesting no transactions
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-02-01T12:00:00"\n"redbark_balances_2026.csv" = "2000-01-01T00:00:00"\n"_redbark_transactions.csv" = "2026-02-02T09:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
