#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a tab sorted by hand is not an edit: rows are matched on their id, never their position
refresh_write_fixture 0 0 "" 0 -1
