#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an idle standard run makes one Drive listing and one sheet read and uploads nothing
refresh_write_fixture 0 0 "" 0 -1
