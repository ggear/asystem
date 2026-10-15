#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a transaction held on both a closed card and the card replacing it under one name is a warning
refresh_write_fixture 0 0 "" 0 -1
