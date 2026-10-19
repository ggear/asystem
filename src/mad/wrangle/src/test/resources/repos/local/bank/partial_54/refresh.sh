#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a linked balance moving more than its held transactions explain is unreconciled once, while one explained only by a transaction in flight or posted the same day, and an unsettled reading, are not
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
