#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a new AMEX export of two cards is mapped by overlap, renamed and imported: new rows added negated with their posted dates, three same-day repeats kept, held rows and their split kept exactly with their posted dates filled
refresh_write_fixture 0 0 "" 0 -1
