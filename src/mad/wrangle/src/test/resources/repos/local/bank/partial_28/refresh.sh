#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, month end spend by bucket and category: labelled by the next month's first, the current month left out, quiet months zero filled and refunds netting
refresh_write_fixture 0 0 "" 0 -1
