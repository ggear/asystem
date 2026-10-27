#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an export spanning a year whose manual file is unreadable imports the other year but is not recorded as imported
refresh_write_fixture 0 0 "" 2 -1
