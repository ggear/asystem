#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a held row inside an export's dates that no export lists is gone, and one near a listed row of the same amount is also suspect
refresh_write_fixture 0 0 "" 0 -1
