#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual balance dated in the year before its file's is an error holding the file's year
refresh_write_fixture 0 0 "" 1 -1
