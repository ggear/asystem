#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a held transaction inside the window that Redbark no longer lists is kept and counted as suspect, while one posted inside the window but made before it, so not listed, is not
refresh_write_fixture 0 0 "" 1 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
