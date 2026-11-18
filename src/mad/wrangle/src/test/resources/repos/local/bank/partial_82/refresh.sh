#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a linked balance break is still an error when the charges dated after the reading would push it past the cap on those in flight
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
