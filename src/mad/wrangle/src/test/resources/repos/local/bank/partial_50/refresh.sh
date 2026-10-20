#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, with the tab unchanged a normal run re-derives the files that changed: a ticked uncategorised row gains a category and loses the tick, and a manual description edited on Drive is reclassified with no reprocess
refresh_write_fixture 0 0 "" 0 -1
