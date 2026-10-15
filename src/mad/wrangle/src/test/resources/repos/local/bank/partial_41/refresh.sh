#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a reclassified transaction loses its tick on a forced reprocess, while one whose manual category holds and one whose category stands keep theirs
refresh_write_fixture 0 0 "" 0 -1
