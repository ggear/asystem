#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Ensure last run data dir is populated, then clean and repopulate test data from last run
refresh_download
rm -rf "${REPO_TEST_DIR}"/*
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;

# Add cache files
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -name '_database_*.csv' ! -name '*_run.csv' ! -name '_database_equity.csv' -exec cp -vpf {} "${REPO_TEST_DIR}" \;
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -name '_sheet_*.csv' ! -name '*_run.csv' ! -name '_sheet_prices_history.csv' -exec cp -vpf {} "${REPO_TEST_DIR}" \;

# Add current state
cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}"
sed -i '' 's/\r//' "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv"
ROWS_DELTA=$(($(wc -l <"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv") - 1))

# Write fixture toml
END_DATE=$(tail -n1 "$(ls "${REPO_TEST_DIR}"/yahoo_*.csv 2>/dev/null | sort | tail -1)" | cut -d',' -f1)
FILES_PROCESSED=$(($(find "${REPO_TEST_DIR}" -maxdepth 1 -name "yahoo_*.csv" | wc -l | tr -d ' ') + $(find "${REPO_TEST_DIR}" -maxdepth 1 -name "58861*.pdf" | wc -l | tr -d ' ')))
refresh_write_fixture "${FILES_PROCESSED}" "${ROWS_DELTA}" "${END_DATE}" 0 -1
