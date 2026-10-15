#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, blank statuses trigger the accounts call: a match is linked, two Redbark accounts on one key duplicate, none missing, a linked account Redbark no longer lists marked missing, and an unlisted Redbark account is appended linked below a keyless row left untouched, every account id cell filled or corrected
refresh_write_fixture 0 0 "" 2 -1
printf '\n[mtimes]\n"*" = "2026-01-14T12:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
