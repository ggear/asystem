#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual transaction checks: a file of invalid rows left as is with its year as committed, one error per row, and a valid file's identical pair and unknown category manual kept as suspect
refresh_write_fixture 0 0 "" 9 -1
