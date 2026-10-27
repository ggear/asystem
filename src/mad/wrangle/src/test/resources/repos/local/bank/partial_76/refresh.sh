#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an Accounts tab with a duplicate row holds a changed manual file's year unchecked, its bad vetted left as is and nothing committed
refresh_write_fixture 0 0 "" 0 -1
