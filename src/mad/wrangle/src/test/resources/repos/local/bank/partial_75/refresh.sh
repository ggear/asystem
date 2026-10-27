#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an Accounts tab with a duplicate row leaves the year tab's edits unmerged, the tab not uploaded over them and its base kept
refresh_write_fixture 0 0 "" 0 -1
