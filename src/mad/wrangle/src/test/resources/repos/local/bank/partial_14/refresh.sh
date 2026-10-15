#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an id-less held transaction absorbs at most one live transaction of the same amount within three days, the nearest, by name across a replaced card number, and a transaction posted six days after it was made matched on the day it was made, while a second identical one, one four days away and a new one are kept
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"redbark_balances_2026.csv" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
