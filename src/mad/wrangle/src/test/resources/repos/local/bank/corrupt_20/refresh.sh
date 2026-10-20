#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual balances file with invalid rows left as is, its year held as committed: a linked account's name, an unknown account, a future date and an unparsed value
refresh_write_fixture 0 0 "" 4 -1
