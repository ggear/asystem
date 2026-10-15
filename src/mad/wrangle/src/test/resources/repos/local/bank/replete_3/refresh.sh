#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a usable accounts tab with no committed snapshot, as after an unusable one, re-derives every balance and commits its snapshot
refresh_write_fixture 0 0 "" 0 -1
