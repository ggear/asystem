#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the review per year tab of a year with rows both before and in the open month raises a closed months error and an open month warning
refresh_write_fixture 0 0 "" 0 -1
