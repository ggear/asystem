#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual transactions typed on the year tabs: an edit, a deletion, a new row, a date moved across years and an edited placeholder each land in the right manual file, and the placeholders roll to exactly one per manual account this month
refresh_write_fixture 0 0 "" 0 -1
