#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, unsplitting: one copy deleted and the other's amount split set back to the amount restores one whole transaction
refresh_write_fixture 0 0 "" 0 -1
