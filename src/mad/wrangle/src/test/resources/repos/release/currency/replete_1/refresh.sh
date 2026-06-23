#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.bash"
refresh_setup "$0" "currency" "release"

# Ensure last run data dir is populated, then clean and repopulate test data from last run
refresh_download
refresh_repopulate

# Touch data files
find "${REPO_TEST_DIR}" -maxdepth 1 -name "*.xls" -exec touch {} \;

# Add current state trimmed by 1 last row so rows_delta=1
cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}"
END_DATE=$(tail -n1 "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv" | cut -d',' -f1)
sed '$d' "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv" | tr -d '\r' >"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv.tmp"
mv "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv.tmp" "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv"
ROWS_DELTA=1

# Write fixture toml
FILES_PROCESSED=$(($(find "${REPO_TEST_DIR}" -maxdepth 1 -name "*.xls" | wc -l | tr -d ' ')))
refresh_write_fixture "${FILES_PROCESSED}" "${ROWS_DELTA}" "${END_DATE}" 0 -1
