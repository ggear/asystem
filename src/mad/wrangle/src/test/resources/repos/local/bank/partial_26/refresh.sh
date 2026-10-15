#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a tab edited between the read and the upload is not overwritten: its upload and every later one is skipped
refresh_write_fixture 0 0 "" 0 -1
