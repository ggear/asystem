#!/usr/bin/env bash

REPO_RUN_DIR="${HOME}/Code/asystem/src/mad/wrangle/target/data/equity"

REPO_TEST_DIR="$(cd "$(dirname "$0")" && pwd)/$(basename "$0" .sh)"
if [ ! -f "${REPO_RUN_DIR}/__equity_current.csv" ]; then
  echo "Error: ${REPO_RUN_DIR}/__equity_current.csv does not exist, test needs to be run to prime data" >&2
  exit 1
fi

# Copy all data files
find "${REPO_TEST_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec rm -f {} \;
find "${REPO_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec cp -vfp {} "${REPO_TEST_DIR}"/ \;

# Remove current month files and any previous year month files
rm -v "${REPO_TEST_DIR}/yahoo_"*"_$(date +%Y)-$(date +%m).csv"
for f in "${REPO_TEST_DIR}/yahoo_"*_[0-9][0-9][0-9][0-9]-[0-9][0-9].csv; do
  [[ "$f" != *_$(date +%Y)-* ]] && rm -v "$f"
done

# Add current state, trimmed to exclude current month rows
cp -vf "${REPO_RUN_DIR}/__equity_current.csv" "${REPO_TEST_DIR}"
DATE_CURRENT_MONTH=$(date +%Y-%m)
CURRENT_MONTH_FIRST_LINE=$(grep -n "^${DATE_CURRENT_MONTH}" "${REPO_TEST_DIR}/__equity_current.csv" | head -1 | cut -d: -f1)
if [ -n "$CURRENT_MONTH_FIRST_LINE" ]; then
  head -n "$((CURRENT_MONTH_FIRST_LINE - 1))" "${REPO_TEST_DIR}/__equity_current.csv" | tr -d '\r' > "${REPO_TEST_DIR}/__equity_current.csv.tmp" \
    && mv "${REPO_TEST_DIR}/__equity_current.csv.tmp" "${REPO_TEST_DIR}/__equity_current.csv"
fi
