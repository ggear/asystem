#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, rejected transaction edits, each a data error reverted by the rewrite: a linked row's description, a new row for a linked account and a split not summing to its amount
refresh_write_fixture 0 0 "" 3 -1
