#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a transactions file in an earlier column order and amount format and a balances file in an earlier amount format, whose rows a forced reprocess leaves unchanged, are rewritten in the current form
refresh_write_fixture 0 0 "" 0 -1
