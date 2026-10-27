# shellcheck shell=bash
# shellcheck disable=SC2034

REFRESH_LOG_SEP="------------------------------------------------------------"
REFRESH_LOG_RED=$'\033[31m'
REFRESH_LOG_GREEN=$'\033[32m'
REFRESH_LOG_RESET=$'\033[00m'

WRANGLE_DIR="${HOME}/Code/asystem/src/mad/wrangle"
WRANGLE_UNIT_DIR="${WRANGLE_DIR}/src/test/python/unit"
WRANGLE_PYTHON="${HOME}/.pyenv/versions/asystem/bin/python"
WRANGLE_PYTEST="${HOME}/.pyenv/versions/asystem/bin/pytest"

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

# Populate the REPO_TEST_* variables shared by every refresh script from the calling script path alone
# (repos/<scope>/<plugin>/<case>/refresh.sh): plugin name and repo scope are derived from the path.
refresh_setup() {
  REPO_TEST_CASE_DIR="$(cd "$(dirname "$1")" && pwd)"
  REPO_TEST_CASE="$(basename "${REPO_TEST_CASE_DIR}")"
  REPO_TEST_NAME="$(basename "$(dirname "${REPO_TEST_CASE_DIR}")")"
  REPO_TEST_SCOPE="$(basename "$(dirname "$(dirname "${REPO_TEST_CASE_DIR}")")")"
  REPO_TEST_DIR="${REPO_TEST_CASE_DIR}/data"
  REPO_TEST_RUN_DIR="${WRANGLE_DIR}/target/data/${REPO_TEST_NAME}"
  REPO_TEST_FIXTURE_FILE="${REPO_TEST_CASE_DIR}/fixture.toml"
}

# Run the plugin derived from REPO_TEST_NAME against a cache dir, with the module .env loaded as the unit tests do. Pass "online" as the second arg to enable
# live source/drive downloads (RELEASE scope, debug logging); omit or pass "offline" for a fully local run
# (LOCAL scope, warning logging, all downloads disabled). Sheet downloads are enabled online for equity and bank, which read
# manual prices, index weights and the bank input tabs, database downloads for equity only. All uploads always disabled. Pass "force" as the third arg to
# force every download, so a source with a freshness window answers whatever the cache dir's file times say.
refresh_run_plugin() {
  local cache_dir="$1"
  local mode="${2:-offline}"
  local force="${3:-}"
  refresh_python - "${cache_dir}" "${REPO_TEST_NAME}" "${mode}" "${WRANGLE_DIR}/.env" "${force}" << 'PYEOF'
import os, sys, importlib
from wrangle.plugin.config import RepoScope, config, load_profile
cache_dir, plugin_name, mode, env_file, force = sys.argv[1], sys.argv[2], sys.argv[3], sys.argv[4], sys.argv[5]
os.environ.update(load_profile(env_file))
module = importlib.import_module(f"wrangle.plugin.{plugin_name}.{plugin_name}")
online = mode == "online"
config.log_level = "debug"
config.repo_scope = RepoScope.RELEASE if online else RepoScope.LOCAL
config.cache_dir = cache_dir
config.force_reprocessing = True
config.force_downloads = force == "force"
config.force_uploads = False
config.disable_drive_uploads = True
config.disable_sheet_uploads = True
config.disable_database_uploads = True
config.disable_drive_downloads = not online
config.disable_source_downloads = not online
config.disable_sheet_downloads = not online or plugin_name not in ("equity", "bank")
config.disable_database_downloads = not online or plugin_name != "equity"
getattr(module, plugin_name.capitalize())().run()
PYEOF
}

# Populate REPO_TEST_RUN_DIR (${base}/${plugin}, the plugin's local cache) with a fresh live cache. The cache is
# first primed from the committed test data dir so the online run is incremental (equity re-downloads only the
# current period rather than every ticker-year), mirroring the deleted *_download unit test's _load_caches step.
refresh_download() {
  rm -rf "${REPO_TEST_RUN_DIR}"
  mkdir -p "${REPO_TEST_RUN_DIR}"
  if [ -d "${REPO_TEST_DIR}" ]; then
    find "${REPO_TEST_DIR}" -mindepth 1 -maxdepth 1 ! -name '.git*' ! -name '~$*' -exec cp -Rpf {} "${REPO_TEST_RUN_DIR}/" \;
  fi
  refresh_run_plugin "$(dirname "${REPO_TEST_RUN_DIR}")" online
}

# Clean the test data dir of its source files and repopulate them from the last run, preserving underscore-prefixed caches.
refresh_repopulate() {
  find "${REPO_TEST_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec rm -f {} \;
  find "${REPO_TEST_RUN_DIR}" -maxdepth 1 -type f -name '[!_]*' -exec cp -vpf {} "${REPO_TEST_DIR}"/ \;
}

# Write the error-case fixture: no data, no delta, expected errors derived from the case name.
refresh_error_case() {
  refresh_write_fixture 0 0 "" "$(refresh_expected_errors)" -1
}

# Download, repopulate, then bake a rows_delta=1 replete fixture for a simple single-snapshot plugin:
# touch the source files named by the first (space-separated) pattern list, copy the current snapshot in,
# trim every row at its latest date so exactly one day is left to add, and write the fixture counting the
# second pattern's files. Both patterns are find -name patterns, expanded by find rather than the shell.
refresh_replete_trimmed() {
  local count_glob="$2" current_file end_date files_processed pattern
  local -a touch_patterns find_expr=()
  set -f
  # shellcheck disable=SC2206
  touch_patterns=($1)
  set +f
  for pattern in "${touch_patterns[@]}"; do
    find_expr+=(-o -name "${pattern}")
  done
  refresh_download
  refresh_repopulate
  find "${REPO_TEST_DIR}" -maxdepth 1 \( -false "${find_expr[@]}" \) -exec touch {} \;
  current_file="${REPO_TEST_DIR}/__${REPO_TEST_NAME}_current.csv"
  cp -vpf "${REPO_TEST_RUN_DIR}/__${REPO_TEST_NAME}_current.csv" "${REPO_TEST_DIR}"
  end_date=$(tail -n1 "${current_file}" | cut -d',' -f1 | tr -d '\r')
  awk -F',' -v end_date="${end_date}" 'NR==1 || $1 < end_date' "${current_file}" | tr -d '\r' >"${current_file}.tmp"
  mv "${current_file}.tmp" "${current_file}"
  files_processed=$(find "${REPO_TEST_DIR}" -maxdepth 1 -name "${count_glob}" | wc -l | tr -d ' ')
  refresh_write_fixture "${files_processed}" 1 "${end_date}" 0 -1
}

# Mirror the test data dir onto the scope's Drive folder through the Drive API, the plugin's own writer, never the Drive desktop mount, which syncs late and
# races the API into a second file of one name. Names the plugin's sync ignores are left out. Each name keeps its oldest copy, updated in place when its
# content differs, and is created only when absent; other copies are trashed, and with "delete" so are names the dir lacks. Fails unless the folder then
# lists each name once with the dir's content.
refresh_drive_mirror() {
  refresh_python - "${REPO_TEST_DIR}" "${REPO_TEST_NAME}" "${REPO_TEST_SCOPE}" "${1:-}" <<'PYEOF'
import collections, glob, hashlib, importlib, os, sys
import google.oauth2.service_account
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload
from wrangle.plugin.config import DRIVE_IGNORE_PREFIXES, get_file
data_dir, plugin_name, scope, mode = sys.argv[1:5]
folder = getattr(importlib.import_module(f"wrangle.plugin.{plugin_name}.{plugin_name}"), f"REPOS_{plugin_name.upper()}")._scopes[scope]["drive_folder"]
credentials = google.oauth2.service_account.Credentials.from_service_account_file(get_file(".google_service_account.json"), scopes=["https://www.googleapis.com/auth/drive"])
files = build("drive", "v3", credentials=credentials, cache_discovery=False).files()
def listed():
    by_name, token = collections.defaultdict(list), None
    while True:
        response = files.list(q=f"'{folder}' in parents and trashed = false", spaces="drive", fields="nextPageToken, files(id, name, md5Checksum, createdTime)", pageSize=1000, pageToken=token).execute()
        for drive_file in response.get("files", []):
            if not drive_file["name"].startswith(DRIVE_IGNORE_PREFIXES):
                by_name[drive_file["name"]].append(drive_file)
        token = response.get("nextPageToken")
        if not token:
            return {name: sorted(copies, key=lambda copy: (copy["createdTime"], copy["id"])) for name, copies in by_name.items()}
local = {
    os.path.basename(path): (path, hashlib.md5(open(path, "rb").read()).hexdigest())
    for path in sorted(glob.glob(f"{data_dir}/*"))
    if os.path.isfile(path) and not os.path.basename(path).startswith((*DRIVE_IGNORE_PREFIXES, "."))
}
counts = collections.Counter()
for name, copies in listed().items():
    for copy in copies[1:] if name in local or mode != "delete" else copies:
        files.update(fileId=copy["id"], body={"trashed": True}).execute()
        counts["trashed"] += 1
drive = listed()
for name, (path, md5) in local.items():
    if name not in drive:
        files.create(body={"name": name, "parents": [folder]}, media_body=MediaFileUpload(path)).execute()
        counts["created"] += 1
    elif drive[name][0].get("md5Checksum") != md5:
        files.update(fileId=drive[name][0]["id"], media_body=MediaFileUpload(path)).execute()
        counts["updated"] += 1
drive = listed()
wrong = sorted(name for name, (_, md5) in local.items() if len(drive.get(name, [])) != 1 or drive[name][0].get("md5Checksum") != md5)
extra = sorted(set(drive) - set(local)) if mode == "delete" else []
print(f"Drive folder [{folder}] mirrored, created [{counts['created']}] updated [{counts['updated']}] trashed [{counts['trashed']}]")
if wrong or extra:
    sys.exit(f"Drive folder [{folder}] does not mirror [{data_dir}], names not listed once with its content [{', '.join(wrong)}], extra [{', '.join(extra)}]")
PYEOF
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
