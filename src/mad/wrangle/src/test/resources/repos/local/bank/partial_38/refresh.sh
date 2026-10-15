#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a replaced card shares its name with the closed card it replaced, both holding transactions on one date without error
refresh_write_fixture 0 0 "" 0 -1
