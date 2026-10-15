#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the first check of a new year writes its opening snapshot of every linked account into a new year file and leaves the previous year's file untouched, a moved balance sweeping the transactions
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2025.csv" = "2026-01-15T11:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
