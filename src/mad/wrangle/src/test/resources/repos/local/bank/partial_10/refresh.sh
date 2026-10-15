#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, two identical history transactions stay two, told apart by their ordinal, each with its pinned id
refresh_write_fixture 0 0 "" 0 -1
