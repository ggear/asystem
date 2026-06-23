#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.bash"
refresh_setup "$0" "equity" "preview"

# Ensure last run data dir is populated, then clean and repopulate test data from last run
refresh_download
rm -rf "${REPO_TEST_DIR}"/*
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;

# Repopulate Drive repo
rsync -avci "${REPO_TEST_DIR}"/ "${REPO_TEST_DRIVE_DIR}"/

# Add cache files
cp -vpf "${REPO_TEST_RUN_DIR}/_sheet_prices_manual.csv" "${REPO_TEST_DIR}"
cp -vpf "${REPO_TEST_RUN_DIR}/_sheet_portfolio_indexes.csv" "${REPO_TEST_DIR}"
cp -vpf "${REPO_TEST_RUN_DIR}/_database_rba_"*_"rates.csv" "${REPO_TEST_DIR}"

# Add current state, trim last line so rows_delta=1 (ie 1 day's row in source files to add)
cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}"
ROWS_BEFORE=$(($(wc -l <"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv") - 1))
sed -i '' 's/\r//; $d' "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv"
ROWS_DELTA=$((ROWS_BEFORE - $(($(wc -l <"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv") - 1))))

# Write fixture toml
END_DATE=$(tail -n1 "$(ls "${REPO_TEST_DIR}"/yahoo_*.csv 2>/dev/null | sort | tail -1)" | cut -d',' -f1)
FILES_PROCESSED=$(($(find "${REPO_TEST_DIR}" -maxdepth 1 -name "yahoo_*.csv" | wc -l | tr -d ' ') + $(find "${REPO_TEST_DIR}" -maxdepth 1 -name "58861*.pdf" | wc -l | tr -d ' ')))
refresh_write_fixture "${FILES_PROCESSED}" "${ROWS_DELTA}" "${END_DATE}" 0 -1
