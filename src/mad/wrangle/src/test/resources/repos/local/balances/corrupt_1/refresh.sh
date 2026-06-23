#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.bash"
refresh_setup "$0" "balances" "local"

# Error-case fixture: source data is not processable, derive expected errors from the case name
refresh_write_fixture 0 0 "" "$(refresh_expected_errors)" -1
