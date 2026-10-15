#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the errors tab lists this run's standing problems and the last thirty days of rejected records, dropping older ones
refresh_write_fixture 0 0 "" 1 -1
