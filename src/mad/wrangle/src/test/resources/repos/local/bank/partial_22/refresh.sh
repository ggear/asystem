#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual transactions in files on Drive: name-only rows given their account ids and amount splits, a row dated in the next year moved to its file, and a file saved by Excel parsed
refresh_write_fixture 0 0 "" 0 -1
