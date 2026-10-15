#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a balances response with no balances is a source error and each linked account absent from it a data error, writing no file
refresh_write_fixture 0 0 "" 1 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
