#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a bucket-only classifier edit clears no tick and logs nothing, the month totals regrouped under the new bucket
refresh_write_fixture 0 0 "" 0 -1
