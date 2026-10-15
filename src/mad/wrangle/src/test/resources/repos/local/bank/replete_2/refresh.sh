#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a changed accounts tab against the committed snapshot and state re-derives every balance and transaction in place, after which reruns are no-ops
refresh_write_fixture 0 0 "" 0 -1
