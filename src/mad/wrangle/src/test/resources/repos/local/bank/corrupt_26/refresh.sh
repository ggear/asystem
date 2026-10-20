#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, manual balance checks: a reading before its account's from date and two entries for one moment leave their file as is, while in another file a liability above zero and a ten-fold jump are kept as suspect
refresh_write_fixture 0 0 "" 5 -1
