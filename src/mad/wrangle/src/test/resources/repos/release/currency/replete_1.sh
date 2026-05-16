#!/usr/bin/env bash

REPO_RUN_DIR="${HOME}/Code/asystem/src/mad/wrangle/target/data/currency"
REPO_TEST_DIR="$(cd "$(dirname "$0")" && pwd)/$(basename "$0" .sh)"

# Check test have been run to prime tes data
if [ ! -f "${REPO_RUN_DIR}/__currency_current.csv" ]; then
  echo "Error: ${REPO_RUN_DIR}/__currency_current.csv does not exist, the release/download test needs to be run first" >&2
  exit 1
fi

# Clean current test files
# TODO: Remove all once database/sheets provisioned
find "${REPO_TEST_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec rm -f {} \;

# Copy all data files
find "${REPO_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec cp -vfp {} "${REPO_TEST_DIR}"/ \;

# Add current state, trimmed to exclude current month rows
cp -vf "${REPO_RUN_DIR}/__currency_current.csv" "${REPO_TEST_DIR}"
DATE_CURRENT_MONTH=$(date +%Y-%m)
CURRENT_MONTH_FIRST_LINE=$(grep -n "^${DATE_CURRENT_MONTH}" "${REPO_TEST_DIR}/__currency_current.csv" | head -1 | cut -d: -f1)
if [ -n "$CURRENT_MONTH_FIRST_LINE" ]; then
  head -n "$((CURRENT_MONTH_FIRST_LINE - 1))" "${REPO_TEST_DIR}/__currency_current.csv" | tr -d '\r' >"${REPO_TEST_DIR}/__currency_current.csv.tmp" &&
    mv "${REPO_TEST_DIR}/__currency_current.csv.tmp" "${REPO_TEST_DIR}/__currency_current.csv"
fi
