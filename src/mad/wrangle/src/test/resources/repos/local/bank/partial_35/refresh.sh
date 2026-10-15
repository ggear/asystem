#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a tab read back with its numbers displayed differently is the same tab, so the guard lets the upload go ahead
refresh_write_fixture 0 0 "" 0 -1
