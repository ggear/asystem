#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the first check of a new year compares each reading to the previous year file's latest: none moved, so the opening snapshot is written, transactions requested and none returned
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n"_redbark_transactions.csv" = "2026-01-15T09:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
