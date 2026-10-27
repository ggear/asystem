#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual balance edited on the Balances tab is written to its file on Drive, while an edit to a linked balance is put back
refresh_write_fixture 0 0 "" 0 -1
