#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, classifier standing errors: a bank code not a CDR code, a merchant code not four digits, two code rows for one category and an equal length tie
refresh_write_fixture 0 0 "" 4 -1
