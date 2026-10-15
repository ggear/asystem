#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, two rows for one account on one date make the tab unusable
refresh_write_fixture 0 0 "" 1 -1
