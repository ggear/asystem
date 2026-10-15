#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, accounts, balances and transactions together: a history year file, a live posting held there without a source id, a pending one ignored, the bank and merchant codes stored as codes, and every transaction id pinned
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
