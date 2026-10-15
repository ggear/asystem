#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, classification by the longest literal pattern, then merchant code, then bank code: nested patterns, padded whitespace, a metacharacter, codes and an unmapped income code, forced reprocessing reclassifying every row while a category manual still wins
refresh_write_fixture 0 0 "" 0 -1
