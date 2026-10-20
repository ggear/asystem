#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual row dated in a year whose manual file is unreadable leaves its own file as is, both years held as committed
refresh_write_fixture 0 0 "" 2 -1
