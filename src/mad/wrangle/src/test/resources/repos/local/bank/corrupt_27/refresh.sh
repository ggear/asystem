#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual transaction checks, each rejected: an unparsed amount, an unknown account, a future date, a date before the account's from date, more than two decimals, a zero amount and a blank description; while one identical to another and an unknown category manual are kept as suspect
refresh_write_fixture 0 0 "" 9 -1
