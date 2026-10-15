#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a padded key maps, a version not yet valid keeps the stored name, a blank name and an account at another institution each count
refresh_write_fixture 0 0 "" 2 -1
