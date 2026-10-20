#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an export whose rename fails on Drive keeps its name and is not imported
refresh_write_fixture 0 0 "" 0 -1
