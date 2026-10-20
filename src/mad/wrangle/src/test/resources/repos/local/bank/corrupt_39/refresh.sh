#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an export renamed by hand maps by its name, one of a linked account is not imported, and one of a new card with no overlap is left unrenamed
refresh_write_fixture 0 0 "" 0 -1
