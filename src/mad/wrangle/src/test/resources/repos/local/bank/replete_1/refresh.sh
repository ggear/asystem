#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a type 2 version renames one account from its from date, the changed dimension re-deriving every balance
refresh_write_fixture 0 0 "" 0 -1
