#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual file saved as Windows-1252 is unreadable and holds its year, the run not stopped by the column rename
refresh_write_fixture 0 0 "" 1 -1
