#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, classifier standing errors, one per code: a blank category, a category in two buckets, categories differing only in case, a short pattern, a code list on a pattern row, one pattern in two categories, a pattern matching over the share, and a category in use the tab lacks
refresh_write_fixture 0 0 "" 9 -1
