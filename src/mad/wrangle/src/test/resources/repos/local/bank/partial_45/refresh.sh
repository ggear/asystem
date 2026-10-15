#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a sweep on a normal run writes a transaction Redbark now dates inside the window whose source id an unchanged older year file holds, and the dedupe compares every file, removing it from the changed one
refresh_write_fixture 0 0 "" 1 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
