#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, two accounts holding one name on the same date are both kept
refresh_write_fixture 0 0 "" 1 -1
