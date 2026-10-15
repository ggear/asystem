#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, two otherwise identical linked transactions, the first given a category manual: the rewrite keeps each at its place in the file, so the edited one keeps its own id
refresh_write_fixture 0 0 "" 0 -1
