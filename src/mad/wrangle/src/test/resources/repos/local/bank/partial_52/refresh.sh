#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a held transaction Redbark relists under a new id is adopted, one it no longer lists is kept, one never dated takes Redbark's dates once and one already dated keeps its own
refresh_write_fixture 0 0 "" 2 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
