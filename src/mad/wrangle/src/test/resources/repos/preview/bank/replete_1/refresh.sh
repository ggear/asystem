#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"
BANK_FILE_REGEX='.*/(redbark|manual)_(balances|transactions)_[0-9]{4}\.csv'

# Run once online against release from a clean cache, so the run dir holds release's files and exports as they stand on its Drive, its sheet's input tabs and
# the states those files make
rm -rf "${REPO_TEST_RUN_DIR}"
mkdir -p "${REPO_TEST_RUN_DIR}"
refresh_run_plugin "$(dirname "${REPO_TEST_RUN_DIR}")" online

# Clean and repopulate test data from the run, release's year files and AMEX exports, leaving out the change logs
find "${REPO_TEST_DIR}" -mindepth 1 ! -name '.git*' -delete
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' ! -name 'bank_reclassified_*' -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;
touch "${REPO_TEST_DIR}/.gitkeep"

# Repopulate Drive repo, mirrored exactly since the test syncs it live
refresh_drive_mirror delete

# Add cache files, the release sheet's tabs standing in for the preview sheet's with sheet downloads disabled, only each tab's v1, the download into the
# empty cache, since a later version is the run's own render
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -name '_sheet_bank_*_v1.csv' -exec cp -vpf {} "${REPO_TEST_DIR}" \;

# Add current states, trim each one's last line so rows_delta=1 (ie one row in the year files to add to each state)
for STATE in balances transactions; do
  cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_${STATE}_current.csv" "${REPO_TEST_DIR}"
  sed -i '' 's/\r//; $d' "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_${STATE}_current.csv"
done

# Write fixture toml, the clock pinned to the refresh so the files and states stand as of then
BALANCES_FILE="${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_balances_current.csv"
TRANSACTIONS_FILE="${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_transactions_current.csv"
FILES_PROCESSED=$(find -E "${REPO_TEST_DIR}" -maxdepth 1 -type f -regex "${BANK_FILE_REGEX}" | wc -l | tr -d ' ')
TRANSACTIONS_IDS=$(refresh_python -c 'import sys, polars; print(polars.read_csv(sys.argv[1], infer_schema=False)["Transaction ID"].n_unique())' "${TRANSACTIONS_FILE}")
REFRESH_TODAY="$(date +%Y-%m-%dT%H:%M:%S)"
refresh_write_fixture "${FILES_PROCESSED}" 1 "$(refresh_last_date "${BALANCES_FILE}")" 0 -1
printf 'transactions_rows_delta = 1\ntransactions_rows = %s\ntransactions_end_date = "%s"\ntransactions_ids = %s\ntoday = "%s"\n' \
  "$(($(wc -l <"${TRANSACTIONS_FILE}") - 1))" "$(refresh_last_date "${TRANSACTIONS_FILE}")" "${TRANSACTIONS_IDS}" "${REFRESH_TODAY}" >>"${REPO_TEST_FIXTURE_FILE}"
printf '\n[mtimes]\n"*" = "%s"\n' "${REFRESH_TODAY}" >>"${REPO_TEST_FIXTURE_FILE}"
