#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an account type outside the two and a status outside the vocabulary each count a source error, the type read as an asset
refresh_write_fixture 0 0 "" 2 -1
