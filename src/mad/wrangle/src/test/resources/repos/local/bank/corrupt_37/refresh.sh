#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a year file changed on Drive mid-run conflicts on the sync and keeps its tab, base, change log and committed record back
refresh_write_fixture 0 0 "" 0 -1
