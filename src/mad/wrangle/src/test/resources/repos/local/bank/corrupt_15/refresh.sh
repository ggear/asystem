#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an unreadable year file is kept and counts an errored file, its year left as committed while another year commits
refresh_write_fixture 0 0 "" 1 -1
