#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual category equal to the row's category keeps its tick and a different one clears it; a stale tab cannot re-tick a moved row but can untick one
refresh_write_fixture 0 0 "" 0 -1
