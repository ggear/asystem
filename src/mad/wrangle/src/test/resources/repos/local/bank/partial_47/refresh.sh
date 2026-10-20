#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a classifier edit re-derives every row on the next run: a moved vetted row loses its tick and one marked No keeps it, a manual row keeps it, an unmatched row is blanked, each cleared tick logged in the run's month
refresh_write_fixture 0 0 "" 0 -1
