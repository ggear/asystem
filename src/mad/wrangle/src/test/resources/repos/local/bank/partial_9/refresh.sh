#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the balances tab holds every reading of the current and previous months and each active account's latest older one, sorted by account then newest first, a closed account dropping off
refresh_write_fixture 0 0 "" 0 -1
