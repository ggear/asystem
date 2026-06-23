REFRESH_LOG_SEP="------------------------------------------------------------"
REFRESH_LOG_RED=$'\033[31m'
REFRESH_LOG_GREEN=$'\033[32m'
REFRESH_LOG_RESET=$'\033[00m'

WRANGLE_DIR="${HOME}/Code/asystem/src/mad/wrangle"
WRANGLE_UNIT_DIR="${WRANGLE_DIR}/src/test/python/unit"
WRANGLE_PYTHON="${HOME}/.pyenv/versions/asystem/bin/python"
WRANGLE_PYTEST="${HOME}/.pyenv/versions/asystem/bin/pytest"
WRANGLE_DRIVE_DIR="/Users/graham/Google Drive/My Drive/Wrangle"

refresh_log_sep() {
  printf '%s\n' "$REFRESH_LOG_SEP"
}

refresh_log_block() {
  printf '\n'
  refresh_log_sep
  printf '%s%s%s\n' "$2" "$1" "$REFRESH_LOG_RESET"
  refresh_log_sep
  printf '\n'
}

refresh_log_error() {
  refresh_log_block "Error: $1" "$REFRESH_LOG_RED" >&2
}

refresh_log_warning() {
  printf '%sWarning: %s%s\n' "$REFRESH_LOG_RED" "$1" "$REFRESH_LOG_RESET"
}

refresh_log_success() {
  printf '%sSuccess: %s%s\n' "$REFRESH_LOG_GREEN" "$1" "$REFRESH_LOG_RESET"
}

# Populate the REPO_TEST_* variables shared by every refresh script from the calling script path (<case>/refresh.sh), plugin name and repo scope.
refresh_setup() {
  REPO_TEST_NAME="$2"
  REPO_TEST_SCOPE="$3"
  REPO_TEST_CASE_DIR="$(cd "$(dirname "$1")" && pwd)"
  REPO_TEST_CASE="$(basename "${REPO_TEST_CASE_DIR}")"
  REPO_TEST_DIR="${REPO_TEST_CASE_DIR}/data"
  REPO_TEST_RUN_DIR="${WRANGLE_DIR}/target/data/${REPO_TEST_NAME}"
  REPO_TEST_FIXTURE_FILE="${REPO_TEST_CASE_DIR}/fixture.toml"
  REPO_TEST_DRIVE_DIR="${WRANGLE_DRIVE_DIR}/${REPO_TEST_NAME}/${REPO_TEST_SCOPE}/data"
}

# Run the plugin's download unit test to populate REPO_TEST_RUN_DIR with a fresh live data cache.
refresh_download() {
  (cd "${WRANGLE_UNIT_DIR}" &&
    PYTHONUNBUFFERED=1 "${WRANGLE_PYTEST}" -s unit_test.py::"WrangleTest::test_${REPO_TEST_NAME}_release_${REPO_TEST_CASE}_download") ||
    { refresh_log_error "unit test failed" && exit $?; }
}

# Clean the test data dir of its source files and repopulate them from the last run, preserving underscore-prefixed caches.
refresh_repopulate() {
  find "${REPO_TEST_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec rm -f {} \;
  find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;
}

# Run the project python with the wrangle package importable from any directory.
refresh_python() {
  PYTHONPATH="${WRANGLE_DIR}/src/main/python${PYTHONPATH:+:$PYTHONPATH}" "${WRANGLE_PYTHON}" "$@"
}

# Echo 1 for corrupt cases, 0 otherwise, derived from the case name.
refresh_expected_errors() {
  case "${REPO_TEST_CASE}" in
  corrupt*) printf '1' ;;
  *) printf '0' ;;
  esac
}

# Echo the earliest first-data-date (row 2, column 1) across the given csv files.
refresh_first_date() {
  local file date earliest=""
  for file in "$@"; do
    [ -f "$file" ] || continue
    date=$(sed -n '2p' "$file" | cut -d',' -f1 | tr -d '\r')
    if [ -n "$date" ] && { [ -z "$earliest" ] || [[ "$date" < "$earliest" ]]; }; then earliest="$date"; fi
  done
  printf '%s' "$earliest"
}

# Echo the latest last-data-date (final row, column 1) across the given csv files.
refresh_last_date() {
  local file date latest=""
  for file in "$@"; do
    [ -f "$file" ] || continue
    date=$(tail -n1 "$file" | cut -d',' -f1 | tr -d '\r')
    if [ -n "$date" ] && { [ -z "$latest" ] || [[ "$date" > "$latest" ]]; }; then latest="$date"; fi
  done
  printf '%s' "$latest"
}

# Echo the inclusive calendar-day count between two ISO dates, mirroring the plugins' contiguous-day forward fill.
refresh_date_span() {
  if [ -z "$1" ] || [ -z "$2" ]; then
    printf '0'
    return
  fi
  refresh_python -c "import sys, datetime; first = datetime.date.fromisoformat(sys.argv[1]); last = datetime.date.fromisoformat(sys.argv[2]); print((last - first).days + 1)" "$1" "$2"
}

# Derive fixture values for an equity test dir by querying its present yahoo_*.csv source files (no plugin run).
# Sets EQUITY_FILES_PROCESSED (distinct ticker-year, mirroring the month/year collapse), EQUITY_ROWS_DELTA (contiguous
# calendar-day span), EQUITY_END_DATE (latest date) and EQUITY_COLS_DATA (tickers * len(DIMENSIONS_STATE), or -1 when empty).
refresh_query_equity() {
  local cols_per_ticker tickers
  EQUITY_FILES_PROCESSED=$(find "${REPO_TEST_DIR}" -maxdepth 1 -name 'yahoo_*.csv' -exec basename {} \; | sed -E 's/^yahoo_([a-z0-9]+)_([0-9]{4}).*/\1_\2/' | sort -u | grep -c . || true)
  EQUITY_END_DATE=$(refresh_last_date "${REPO_TEST_DIR}"/yahoo_*.csv)
  EQUITY_ROWS_DELTA=$(refresh_date_span "$(refresh_first_date "${REPO_TEST_DIR}"/yahoo_*.csv)" "${EQUITY_END_DATE}")
  tickers=$(find "${REPO_TEST_DIR}" -maxdepth 1 -name 'yahoo_*.csv' -exec basename {} \; | sed -E 's/^yahoo_([a-z0-9]+)_.*/\1/' | sort -u | grep -c . || true)
  if [ "${tickers}" -gt 0 ]; then
    cols_per_ticker=$(refresh_python -c "from wrangle.plugin.equity.equity import DIMENSIONS_STATE; print(len(DIMENSIONS_STATE))")
    EQUITY_COLS_DATA=$((tickers * cols_per_ticker))
  else
    EQUITY_COLS_DATA=-1
  fi
}

# Write the five-field fixture toml: files_processed rows_delta end_date expected_errors cols_data.
refresh_write_fixture() {
  printf 'files_processed = %s\nrows_delta = %s\nend_date = "%s"\nexpected_errors = %s\ncols_data = %s\n' \
    "$1" "$2" "$3" "$4" "$5" >"${REPO_TEST_FIXTURE_FILE}"
  printf '==> %s\n' "${REPO_TEST_FIXTURE_FILE}"
}
