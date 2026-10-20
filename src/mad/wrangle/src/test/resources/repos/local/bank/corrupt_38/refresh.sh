#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the weekly sweep checks ninety days: a held row gone, one relisted, one dated, an unheld one raised, a repeat not adopted and nothing added
refresh_write_fixture 0 0 "" 0 -1
