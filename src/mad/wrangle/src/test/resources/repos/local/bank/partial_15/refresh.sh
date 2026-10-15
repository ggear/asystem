#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, split parts are derived on read: -1000, -500, -500 is one whole transaction and one split in two parts sharing an id
refresh_write_fixture 0 0 "" 0 -1
