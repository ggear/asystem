#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, two numbers share a name in sequence without error, a third account on no accounts row is unmapped
refresh_write_fixture 0 0 "" 1 -1
