#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an AMEX export imported for each of two cards carries a balance to today, the last one entered for a card holding one and zero for one with none, and the carried balance not moving with the imported charge is a warning in the current month
refresh_write_fixture 0 0 "" 0 -1
