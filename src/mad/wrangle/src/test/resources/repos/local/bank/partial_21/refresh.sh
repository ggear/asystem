#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual balances typed on the balances tab: a value set on a carried reading makes it real, a changed one is saved, a cleared one deleted and a new row with a blank date and time lands at the end of today, the carried readings following
refresh_write_fixture 0 0 "" 0 -1
