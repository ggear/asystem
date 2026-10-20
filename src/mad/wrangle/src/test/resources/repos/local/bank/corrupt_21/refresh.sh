#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, rejected tab edits, each a data error put back by the re-render: a description edited on a row, a row typed without a transaction id and a split not summing to its amount
refresh_write_fixture 0 0 "" 3 -1
