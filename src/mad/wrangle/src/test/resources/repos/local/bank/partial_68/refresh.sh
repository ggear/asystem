#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a held description and a note holding spreadsheet error values, each raised as a standing warning
refresh_write_fixture 0 0 "" 0 -1
