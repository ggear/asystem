#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Synthetic fixture: hand-written data, a first live check with no files: the weekly accounts call appends the unlisted Redbark account, the opening snapshot of both is written and sweeps the transactions, which have none
refresh_write_fixture 0 0 "" 0 -1
printf '\n[mtimes]\n"*" = "2000-01-01T00:00:00"\n' >>"${REPO_TEST_FIXTURE_FILE}"
