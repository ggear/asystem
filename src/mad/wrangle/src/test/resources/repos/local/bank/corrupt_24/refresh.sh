#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a balance whose freshness is not fresh is a standing source error, the reading still stored
refresh_write_fixture 0 0 "" 1 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
