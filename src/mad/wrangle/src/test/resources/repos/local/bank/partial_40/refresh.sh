#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, vetted typed on a linked account's rows: a tick is saved, a category change clears a tick left as it was but keeps one set with it and a No left as it was, an unknown value is rejected and reverted, and a value is saved title cased
refresh_write_fixture 0 0 "" 0 -1
