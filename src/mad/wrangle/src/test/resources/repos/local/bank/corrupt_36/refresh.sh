#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an edit on a row no file holds is unmatched, a tab cut short yields no edit, a split edited on a tab sorted another way changes the right parts, and moved buckets are no edit
refresh_write_fixture 0 0 "" 0 -1
