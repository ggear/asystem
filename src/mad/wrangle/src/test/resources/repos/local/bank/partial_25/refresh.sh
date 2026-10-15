#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, the plugin's own uploads read back as no edit: every run sees the tabs moved and compares them, and the rerun uploads nothing
refresh_write_fixture 0 0 "" 0 -1
