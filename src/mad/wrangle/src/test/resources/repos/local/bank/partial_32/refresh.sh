#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an accounts tab edited after the read is not written: the blank status found by the call is left for the next run
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
