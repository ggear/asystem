#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, after their import a standard run reads only an export edited on Drive, so a row deleted from the year file stays deleted
refresh_write_fixture 0 0 "" 0 -1
