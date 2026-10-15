#!/usr/bin/env bash
set -euo pipefail
source "$(cd "$(dirname "$0")" && pwd)/../../../refresh_lib.sh"
refresh_setup "$0"
BANK_FILE_REGEX='.*/(redbark|manual)_(balances|transactions)_[0-9]{4}\.csv'

# Download from the release Drive, sheet and live source, then drop the newest data so the test always fetches it afresh: the current month's readings of the
# balances year file and the last two weeks of every transactions year file, with the Redbark response caches that would hold the sweeps back
refresh_download
refresh_repopulate
rm -f "${REPO_TEST_DIR}/_redbark_transactions.csv" "${REPO_TEST_DIR}/_redbark_accounts.csv"
refresh_python - "${REPO_TEST_DIR}" "$(date -v-14d +%Y-%m-%d)" "$(date +%Y-%m-01)" <<'PYEOF'
import glob, os, sys
import polars
for path in glob.glob(f"{sys.argv[1]}/redbark_transactions_*.csv"):
    polars.read_csv(path, infer_schema=False).filter(polars.col("Date") < sys.argv[2]).write_csv(path)
balances_path = f"{sys.argv[1]}/redbark_balances_{sys.argv[3][:4]}.csv"
if os.path.isfile(balances_path):
    balances = polars.read_csv(balances_path, infer_schema=False).filter(polars.col("Date") < sys.argv[3])
    if balances.height:
        balances.write_csv(balances_path)
    else:
        os.remove(balances_path)
PYEOF
touch "${REPO_TEST_DIR}/.gitkeep"

# Rebuild both current states offline from the trimmed files, so the live downloads are the only delta
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

# Write fixture toml, the trimmed balances file stale so the test's live balance check and transaction sweep are due
FILES_PROCESSED=$(find -E "${REPO_TEST_DIR}" -maxdepth 1 -type f -regex "${BANK_FILE_REGEX}" | wc -l | tr -d ' ')
refresh_write_fixture "${FILES_PROCESSED}" 1 "$(refresh_last_date "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_balances_current.csv")" 0 -1
printf 'transactions_rows_delta = 1\ntransactions_end_date = "%s"\n' \
  "$(refresh_last_date "${REPO_TEST_DIR}/__${REPO_TEST_NAME}_transactions_current.csv")" >>"${REPO_TEST_FIXTURE_FILE}"
printf '\n[mtimes]\n"redbark_balances_%s.csv" = "2000-01-01T00:00:00"\n' "$(date +%Y)" >>"${REPO_TEST_FIXTURE_FILE}"
