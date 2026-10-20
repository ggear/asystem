#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a run stopped at the first shared call of a later block and run again ends as an uninterrupted run does
refresh_write_fixture 0 0 "" 0 -1
