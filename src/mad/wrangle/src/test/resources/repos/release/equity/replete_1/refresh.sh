#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Ensure last run data dir is populated, then clean and repopulate test data from last run
refresh_download
if [ "$(date +%m)" != "$(date -v+1d +%m)" ]; then
  refresh_log_error "cannot replete ${REPO_TEST_NAME} release on the last day of the month"
  exit 1
fi
rm -rf "${REPO_TEST_DIR}"/*
refresh_repopulate

# Remove last month files
rm -v "${REPO_TEST_DIR}/yahoo_"*"_$(date +%Y)-$(date +%m).csv"

# Add current state, trimmed to exclude current month rows, so rows_delta>=1 (ie at least 1 day's row from this month to add)
cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}"
ROWS_BEFORE=$(($(wc -l <"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv") - 1))
DATE_CURRENT_MONTH=$(date +%Y-%m)
CURRENT_MONTH_FIRST_LINE=$(awk -v month="${DATE_CURRENT_MONTH}" 'index($0, month) == 1 { print NR; exit }' "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv")
if [ -n "$CURRENT_MONTH_FIRST_LINE" ]; then
  head -n "$((CURRENT_MONTH_FIRST_LINE - 1))" "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv" | tr -d '\r' >"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv.tmp" &&
    mv "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv.tmp" "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv"
fi
ROWS_DELTA=$((ROWS_BEFORE - $(($(wc -l <"${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv") - 1))))

# Write fixture toml
END_DATE=$(tail -n1 "$(ls "${REPO_TEST_DIR}"/yahoo_*.csv 2>/dev/null | sort | tail -1)" | cut -d',' -f1)
FILES_PROCESSED=$(($(find "${REPO_TEST_DIR}" -maxdepth 1 -name "yahoo_*.csv" | wc -l | tr -d ' ') + $(find "${REPO_TEST_DIR}" -maxdepth 1 -name "58861*.pdf" | wc -l | tr -d ' ')))
refresh_write_fixture "${FILES_PROCESSED}" "${ROWS_DELTA}" "${END_DATE}" 0 -1
