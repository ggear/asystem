#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an export with a wrong header, an unparsed date or three decimals is left unrenamed and unimported
refresh_write_fixture 0 0 "" 0 -1
