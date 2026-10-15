#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the first due check of a day sweeps the transactions though no balance moved
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2026-01-15T09:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
