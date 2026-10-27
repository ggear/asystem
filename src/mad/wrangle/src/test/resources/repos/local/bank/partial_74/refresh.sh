#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, files written before the derived and linked columns were renamed auto have their headers renamed in place, every value kept
refresh_write_fixture 0 0 "" 0 -1
