#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a card's manual balances against its transactions: a break into a closed month is an error, a closed month with no balance is an error, and a break in the current month a warning
refresh_write_fixture 0 0 "" 0 -1
