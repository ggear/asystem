#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, no accounts tab, every reading keeps its stored name without error
refresh_write_fixture 0 0 "" 0 -1
