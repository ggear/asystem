#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an unchanged tab and committed file with a category no rule produces: a standard run leaves it and logs nothing
refresh_write_fixture 0 0 "" 0 -1
