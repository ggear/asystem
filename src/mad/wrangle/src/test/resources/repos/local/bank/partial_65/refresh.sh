#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, after their import a forced download reads every export again, bringing back a row deleted from the year file
refresh_write_fixture 0 0 "" 0 -1
