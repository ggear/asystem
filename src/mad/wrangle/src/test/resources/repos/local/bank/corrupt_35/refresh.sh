#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a classifier edit with a pattern in two categories is held on a reprocess too, every row re-derived with the last applied tab
refresh_write_fixture 0 0 "" 0 -1
