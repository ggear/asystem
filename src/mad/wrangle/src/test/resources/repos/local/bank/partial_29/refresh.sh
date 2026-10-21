#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the errors tab lists errors first then warnings, each newest first: a standing problem raised again keeps its first date, one no longer raised and a record from an earlier run are historic warnings for thirty days from the date last raised, older ones dropped; rows saved before the state and date raised columns still load
refresh_write_fixture 0 0 "" 1 -1
