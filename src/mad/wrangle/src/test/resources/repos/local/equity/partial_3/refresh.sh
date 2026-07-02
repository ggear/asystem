#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"

# Regenerate synthetic fixture: state baked against the original 2024 file, then the shipped 2024 file revised,
# so an incremental run must reprocess the predecessor 2023 file to correct the year-boundary interpolations
TEMP_DIR=$(mktemp -d)
trap 'rm -rf "${TEMP_DIR}"' EXIT
mkdir -p "${TEMP_DIR}/${REPO_TEST_NAME}"
cp -r "${REPO_TEST_CASE_DIR}/state/." "${TEMP_DIR}/${REPO_TEST_NAME}/"
refresh_run_plugin "${TEMP_DIR}"
cp "${TEMP_DIR}/${REPO_TEST_NAME}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}/"

# Write fixture toml: incremental run processes the new 2024 file plus its 2023 predecessor, delta is the
# three re-interpolated non-trading days (12-30, 12-31, 01-01) plus the four revised 2024 trading days
refresh_write_fixture 2 7 "2024-01-05" 0 17
