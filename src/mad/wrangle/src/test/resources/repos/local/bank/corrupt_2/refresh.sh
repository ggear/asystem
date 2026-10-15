#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a file with a row lacking its account id errors that file only
refresh_write_fixture 0 0 "" 1 -1
