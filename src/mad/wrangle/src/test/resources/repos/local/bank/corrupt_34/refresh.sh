#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a failed drive sync leaves the run's changes unlogged and raises an error, the classifier edit still applied
refresh_write_fixture 0 0 "" 0 -1
