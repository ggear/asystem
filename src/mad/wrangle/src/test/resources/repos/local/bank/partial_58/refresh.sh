#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a category manual and an untick edited on the tab against its base are taken by the file, the tab not re-uploaded, each logged
refresh_write_fixture 0 0 "" 0 -1
