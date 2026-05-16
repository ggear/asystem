#!/usr/bin/env bash

REPO_RUN_DIR="${HOME}/Code/asystem/src/mad/wrangle/src/test/resources/repos/release/interest/replete_1"
REPO_TEST_DIR="$(cd "$(dirname "$0")" && pwd)/$(basename "$0" .sh)"

# Clean current test files
rm -f "${REPO_TEST_DIR}/"*

# Copy all data files
find "${REPO_RUN_DIR}" -maxdepth 1 -type f -exec cp -vfp {} "${REPO_TEST_DIR}"/ \;

# Add current state, trimmed of last line
if [ -s "${REPO_TEST_DIR}/__interest_current.csv" ]; then
  sed -i '' 's/\r//; $d' "${REPO_TEST_DIR}/__interest_current.csv"
fi
