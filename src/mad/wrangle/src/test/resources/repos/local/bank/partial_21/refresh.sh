#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual balances in a file on Drive: a name-only row given its account id and the end of its day, a day-first date and a dollar amount parsed, the carried readings following, and an emptied year file kept header-only
refresh_write_fixture 0 0 "" 0 -1
