#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an export overlapping an imported one by its first days, and a byte-identical copy of it, are mapped by a card seen before and renamed with a suffix, adding the new rows once
refresh_write_fixture 0 0 "" 0 -1
