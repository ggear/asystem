#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a manual file whose rows move into a file itself held by an unreadable year is held in turn, every year left as is
refresh_write_fixture 0 0 "" 3 -1
