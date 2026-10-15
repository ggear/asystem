#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, with the tab unchanged a normal run re-derives the files its edits changed: a ticked uncategorised row gains a category and loses the tick, an edited manual description is reclassified, each change logged by source
refresh_write_fixture 0 0 "" 0 -1
