#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"
BANK_FILE_REGEX='.*/(redbark|manual)_(balances|transactions)_[0-9]{4}\.csv'

# Download from the release Drive, sheet and live source into a clean cache, take its year files and exports, leaving out the caches and change logs, then
# drop the current month's readings of the balances year file so the test always fetches a reading afresh; the transactions year files stay whole, since
# rows Redbark no longer lists (drops, statement history, AMEX imports) exist only there and a trim would lose them
rm -rf "${REPO_TEST_RUN_DIR}"
mkdir -p "${REPO_TEST_RUN_DIR}"
refresh_run_plugin "$(dirname "${REPO_TEST_RUN_DIR}")" online
find "${REPO_TEST_DIR}" -mindepth 1 ! -name '.git*' -delete
find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' ! -name 'bank_reclassified_*' -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;
refresh_python - "${REPO_TEST_DIR}" "$(date +%Y-%m-01)" <<'PYEOF'
import os, sys
import polars
balances_path = f"{sys.argv[1]}/redbark_balances_{sys.argv[2][:4]}.csv"
if os.path.isfile(balances_path):
    balances = polars.read_csv(balances_path, infer_schema=False).filter(polars.col("Date") < sys.argv[2])
    if balances.height:
        balances.write_csv(balances_path)
    else:
        os.remove(balances_path)
PYEOF
touch "${REPO_TEST_DIR}/.gitkeep"

# Rebuild both current states offline from the files, so the live downloads are the only delta
rm -rf "${REPO_TEST_RUN_DIR}"
mkdir -p "${REPO_TEST_RUN_DIR}"
find -E "${REPO_TEST_DIR}" -maxdepth 1 -type f -regex "${BANK_FILE_REGEX}" -exec cp -vpf {} "${REPO_TEST_RUN_DIR}"/ \;
refresh_run_plugin "$(dirname "${REPO_TEST_RUN_DIR}")" offline
for STATE in balances transactions; do
  rm -f "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_${STATE}_current.csv"
  if [ -f "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_${STATE}_current.csv" ]; then
    cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_${STATE}_current.csv" "${REPO_TEST_DIR}"
  fi
done

# Write fixture toml; the test pins its clock past the balance check interval, so its live balance check and transaction fetch are due whatever time the
# Drive sync gives the balances file
FILES_PROCESSED=$(find -E "${REPO_TEST_DIR}" -maxdepth 1 -type f -regex "${BANK_FILE_REGEX}" | wc -l | tr -d ' ')
refresh_write_fixture "${FILES_PROCESSED}" 1 "$(refresh_last_date "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_balances_current.csv")" 0 -1
printf 'transactions_rows_delta = 1\ntransactions_end_date = "%s"\n' \
  "$(refresh_last_date "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_transactions_current.csv")" >>"${REPO_TEST_FIXTURE_FILE}"
