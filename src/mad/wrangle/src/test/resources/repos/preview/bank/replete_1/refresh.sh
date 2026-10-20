#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"
BANK_FILE_REGEX='.*/(redbark|manual)_(balances|transactions)_[0-9]{4}\.csv'
EXPORT_FILE_REGEX='.*/(activity[^/]*|amex_[^/]*)\.csv'
RELEASE_DRIVE_DIR="${WRANGLE_DRIVE_DIR}/${REPO_TEST_NAME}/release/data"
REFRESH_TODAY="$(date +%Y-%m-%dT%H:%M:%S)"

# Run once online against release from a clean cache, forcing every download, so the run dir holds the release sheet's tabs, the live Redbark responses and the
# states those responses make of release's files
find "${REPO_TEST_DIR}" -mindepth 1 ! -name '.git*' -delete
rm -rf "${REPO_TEST_RUN_DIR}"
mkdir -p "${REPO_TEST_RUN_DIR}"
refresh_run_plugin "$(dirname "${REPO_TEST_RUN_DIR}")" online force

# Test data is release's files and AMEX exports, renamed or not, as they stand on its Drive, mirrored onto the preview Drive, so the test replays the live
# responses onto exactly them and renames and imports the exports there; the sync never uploads an export, so the mirror is what places them
find -E "${RELEASE_DRIVE_DIR}" -maxdepth 1 -type f \( -regex "${BANK_FILE_REGEX}" -o -iregex "${EXPORT_FILE_REGEX}" \) -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;
rsync -avci --delete --exclude ".git*" "${REPO_TEST_DIR}"/ "${REPO_TEST_DRIVE_DIR}"/

# Add cache files, the release sheet's tabs standing in for the preview sheet's with sheet downloads disabled, and the live Redbark responses the test serves
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -name '_sheet_bank_*_v*.csv' ! -name '*_run.csv' -exec cp -vpf {} "${REPO_TEST_DIR}" \;
for RESOURCE in accounts balances transactions; do
  cp -vpf "${REPO_TEST_RUN_DIR}/_redbark_${RESOURCE}.csv" "${REPO_TEST_DIR}"/
done
touch "${REPO_TEST_DIR}/.gitkeep"

# Write fixture toml, expecting the states the online run made, the clock pinned to it, the balances file and the last sweep stale so both are due, and the
# accounts response fresh so the weekly call is not
BALANCES_FILE="${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_balances_current.csv"
TRANSACTIONS_FILE="${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_transactions_current.csv"
FILES_PROCESSED=$(find -E "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -regex "${BANK_FILE_REGEX}" | wc -l | tr -d ' ')
TRANSACTIONS_IDS=$(refresh_python -c 'import sys, polars; print(polars.read_csv(sys.argv[1], infer_schema=False)["Transaction ID"].n_unique())' "${TRANSACTIONS_FILE}")
refresh_write_fixture "${FILES_PROCESSED}" "$(($(wc -l <"${BALANCES_FILE}") - 1))" "$(refresh_last_date "${BALANCES_FILE}")" 0 -1
printf 'transactions_rows_delta = %s\ntransactions_end_date = "%s"\ntransactions_ids = %s\ntoday = "%s"\n' "$(($(wc -l <"${TRANSACTIONS_FILE}") - 1))" \
  "$(refresh_last_date "${TRANSACTIONS_FILE}")" "${TRANSACTIONS_IDS}" "${REFRESH_TODAY}" >>"${REPO_TEST_FIXTURE_FILE}"
printf '\n[mtimes]\n"*" = "%s"\n"redbark_balances_%s.csv" = "2000-01-01T00:00:00"\n"_redbark_transactions.csv" = "2000-01-01T00:00:00"\n' \
  "${REFRESH_TODAY}" "${REFRESH_TODAY:0:4}" >>"${REPO_TEST_FIXTURE_FILE}"
