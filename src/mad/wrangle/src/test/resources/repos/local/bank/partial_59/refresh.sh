#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a row changed on Drive and edited on the tab takes the sheet's cell and keeps the Drive edit's others, and a tab edit on a row Redbark re-dated is applied by its source id
refresh_write_fixture 0 0 "" 0 -1
