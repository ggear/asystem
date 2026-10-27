#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a reprocess with an invalid manual transactions and balances file of the year before keeps that year's committed rows in state
refresh_write_fixture 0 0 "" 2 -1
