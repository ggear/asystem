#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Regenerate synthetic fixture: state baked from the 2022 file only, with 2023 and 2024 files arriving later
# as new downloads, so an incremental run must reprocess the predecessor 2022 file behind the 2023 download
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT
mkdir -p "${TEMP_DIR}/${REPO_TEST_NAME}"
cp -r "${REPO_TEST_CASE_DIR}/state/." "${TEMP_DIR}/${REPO_TEST_NAME}/"
refresh_run_plugin "${TEMP_DIR}"
cp "${TEMP_DIR}/${REPO_TEST_NAME}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}/"

# Write fixture toml: incremental run processes the two new files plus the 2022 predecessor, delta is every
# day from 2022-12-31 (first day after the baked state) through 2024-01-05
refresh_write_fixture 3 371 "2024-01-05" 0 17
