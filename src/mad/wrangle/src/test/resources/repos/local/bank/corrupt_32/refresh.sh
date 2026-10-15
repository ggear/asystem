#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual transaction moved into a year whose manual file is unreadable, and a new row dated in that year, are each rejected as a data error, the moved one kept where it was
refresh_write_fixture 0 0 "" 2 -1
