#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, rejected balance edits, each a data error reverted by the rewrite: a value on a linked row, an unknown account, a future date and an unparsed value
refresh_write_fixture 0 0 "" 4 -1
