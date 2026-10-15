#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, review per year tab: unclassified or unvetted rows in a closed month are an error, only in the current month a warning, a vetted classified year clean, and a vetted value read whatever its case and spacing
refresh_write_fixture 0 0 "" 0 -1
