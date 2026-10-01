#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Regenerate synthetic fixture: each ticker carries a clean September file plus an October file holding only the
# last September bar, the shape Yahoo returns when a month is queried before it has any data, which duplicated
# 2025-09-30 across both files and multiplied the per-ticker full join until the container was OOM killed
REPLETE_DIR="${REPO_TEST_CASE_DIR}/../replete_1/data"
TICKERS="acdc aord axjo"
rm -rf "${REPO_TEST_DIR}"
mkdir -p "${REPO_TEST_DIR}"
for ticker in ${TICKERS}; do
  awk -F',' 'NR==1 || substr($1, 1, 7) == "2025-09"' "${REPLETE_DIR}/yahoo_${ticker}_2025.csv" >"${REPO_TEST_DIR}/yahoo_${ticker}_2025-09.csv"
  awk -F',' 'NR==1 || $1 == "2025-09-30"' "${REPLETE_DIR}/yahoo_${ticker}_2025.csv" >"${REPO_TEST_DIR}/yahoo_${ticker}_2025-10.csv"
done

# Write fixture toml: every September file processes, every October file errors, delta is the September calendar days
refresh_query_equity
refresh_write_fixture "$(find "${REPO_TEST_DIR}" -name 'yahoo_*_2025-09.csv' | wc -l | tr -d ' ')" "${EQUITY_ROWS_DELTA}" "${EQUITY_END_DATE}" \
  "$(find "${REPO_TEST_DIR}" -name 'yahoo_*_2025-10.csv' | wc -l | tr -d ' ')" "${EQUITY_COLS_DATA}"
