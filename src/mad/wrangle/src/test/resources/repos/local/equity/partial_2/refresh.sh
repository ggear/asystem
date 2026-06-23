#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.bash"
refresh_setup "$0" "equity" "local"

# Query the present source data (no plugin run) to derive the fixture
refresh_query_equity
refresh_write_fixture "${EQUITY_FILES_PROCESSED}" "${EQUITY_ROWS_DELTA}" "${EQUITY_END_DATE}" "$(refresh_expected_errors)" "${EQUITY_COLS_DATA}"
