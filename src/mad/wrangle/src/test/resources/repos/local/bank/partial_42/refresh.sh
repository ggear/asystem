#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, an accounts tab holding only its header is filled from Redbark: every account appended linked, a credit card as a liability
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
