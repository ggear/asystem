#!/bin/bash

set -e

# Test environment setup
setup_test_env() {
  TEST_SRC="/tmp/test_source"
  TEST_BACKUP="/tmp/test_backup"
  TEST_LOG="/tmp/test.log"
  mkdir -p "$TEST_SRC" "$TEST_BACKUP"
  echo "test file 1" >"$TEST_SRC/file1.txt"
  echo "test file 2" >"$TEST_SRC/file2.txt"
  mkdir -p "$TEST_SRC/subdir"
  echo "test file 3" >"$TEST_SRC/subdir/file3.txt"
}

# Test cleanup
cleanup_test_env() {
  rm -rf "$TEST_SRC" "$TEST_BACKUP" "$TEST_LOG"
}

# Test cases
test_basic_sync() {
  set +e # Temporarily disable exit on error for test functions
  ./sync.sh -d "$TEST_BACKUP" "$TEST_SRC"
  [ -f "$TEST_BACKUP/$TEST_SRC/file1.txt" ] || return 1
  [ -f "$TEST_BACKUP/$TEST_SRC/file2.txt" ] || return 1
  [ -f "$TEST_BACKUP/$TEST_SRC/subdir/file3.txt" ] || return 1
  local result=$?
  set -e # Re-enable exit on error
  return $result
}

test_deep_verify() {
  set +e # Temporarily disable exit on error for test functions
  ./sync.sh -v -d "$TEST_BACKUP" "$TEST_SRC"
  local result=$?
  set -e # Re-enable exit on error
  return $result
}

# Run tests
run_tests() {
  setup_test_env
  echo "Running basic sync test..."
  if test_basic_sync; then
    echo "########################################"
    echo "Basic sync test: PASSED"
    echo "########################################"
  else
    echo "########################################"
    echo "Basic sync test: FAILED"
    echo "########################################"
  fi

  echo "Running deep verify test..."
  if test_deep_verify; then
    echo "########################################"
    echo "Deep verify test: PASSED"
    echo "########################################"
  else
    echo "########################################"
    echo "Deep verify test: FAILED"
    echo "########################################"
  fi
  cleanup_test_env
}

if [ "${1:-}" = "--test" ]; then
  run_tests
  exit
fi

DEEP_VERIFY=false
PROCESS_COUNT=$(nproc)

# Check write permissions
check_permissions() {
  local path="$1"
  if [ ! -w "$path" ]; then
    echo "ERROR: No write permission for $path"
    exit 1
  fi
}

# Determine log file path based on permissions
check_log_path() {
  local var_log="/var/log"
  local tmp_dir="/tmp"
  local timestamp=$(date +%Y%m%d-%H%M%S)

  if [ -w "$var_log" ]; then
    echo "$var_log/sync-$timestamp.log"
  else
    echo "$tmp_dir/sync-$timestamp.log"
  fi
}

LOG_FILE=$(check_log_path)

echo "Starting sync script at $(date)" | tee -a "$LOG_FILE"

# Cleanup on exit
trap 'rm -f /tmp/sync_file_list.txt /tmp/source_hashes.txt /tmp/sync_hashes.txt' EXIT

BACKUP_DIR="/backup"

FILE_LIST=""
DELETE_OPTION=""
while getopts "vd:f:r" opt; do
  case $opt in
  v)
    DEEP_VERIFY=true
    echo "Deep verification enabled" | tee -a "$LOG_FILE"
    ;;
  d)
    BACKUP_DIR="$OPTARG"
    echo "Sync directory set to: $BACKUP_DIR" | tee -a "$LOG_FILE"
    ;;
  f)
    FILE_LIST="$OPTARG"
    echo "Using provided file list: $FILE_LIST" | tee -a "$LOG_FILE"
    ;;
  r)
    DELETE_OPTION="--delete"
    echo "Delete option enabled" | tee -a "$LOG_FILE"
    ;;
  *) ;;
  esac
done
shift $((OPTIND - 1))

if [ "$#" -lt 1 ]; then
  echo "Usage: $0 [-v] [-d backup_dir] [-f file_list] [-r] <share_dir1> [share_dir2 ...]"
  echo "Options:"
  echo "  -v              Enable deep verification"
  echo "  -d backup_dir   Set custom backup directory"
  echo "  -f file_list    Use specific file list"
  echo "  -r              Remove files in backup that don't exist in source"
  exit 1
fi

# Function to check available space
check_space() {
  echo "Checking available space..." | tee -a "$LOG_FILE"
  total_size=$(du -sc "$@" | tail -1 | cut -f1)
  target_free=$(df -k "${BACKUP_DIR}" | awk 'NR==2 {print $4}')
  echo "Total source size: $total_size KB" | tee -a "$LOG_FILE"
  echo "Available space in ${BACKUP_DIR}: $target_free KB" | tee -a "$LOG_FILE"
  if [ ${target_free} -lt ${total_size} ]; then
    echo "ERROR: Not enough space in ${BACKUP_DIR}" | tee -a "$LOG_FILE"
    exit 1
  fi
  echo "Sufficient space available" | tee -a "$LOG_FILE"
}

# Create file list if not provided
create_file_list() {
  echo "Creating backup file list..." | tee -a "$LOG_FILE"
  if [ -z "$FILE_LIST" ]; then
    echo "Generating file list from directories..." | tee -a "$LOG_FILE"
    find "$@" -type f -o -type d >/tmp/backup_file_list.txt
  else
    echo "Using provided file list from $FILE_LIST" | tee -a "$LOG_FILE"
    cp "$FILE_LIST" /tmp/backup_file_list.txt
  fi
  echo "File list creation completed. Total files: $(wc -l </tmp/backup_file_list.txt)" | tee -a "$LOG_FILE"
}

# Check if directories exist
echo "Checking directory existence..." | tee -a "$LOG_FILE"
for dir in "$@"; do
  if [ ! -d "$dir" ]; then
    echo "ERROR: Source directory $dir doesn't exist" | tee -a "$LOG_FILE"
    exit 1
  fi
  echo "Source directory $dir exists" | tee -a "$LOG_FILE"
done

if [ ! -d "$BACKUP_DIR" ]; then
  echo "ERROR: Target directory doesn't exist" | tee -a "$LOG_FILE"
  exit 1
fi
echo "Target directory $BACKUP_DIR exists" | tee -a "$LOG_FILE"

# Main backup process
check_space "$@"
create_file_list "$@"

# Function to get file count and total size
get_stats() {
  local dir=$1
  local count=$(find "$dir" -type f | wc -l)
  local size
  if ! size=$(du -sk "$dir" | cut -f1); then
    echo "ERROR: Failed to calculate directory size" >&2
    size=0
  fi
  echo "$count $size"
}

# Check backup directory permissions
# Perform rsync with file list
check_permissions "${BACKUP_DIR}"

if [ -n "${DELETE_OPTION}" ]; then
  echo "The following files will be deleted:" | tee -a "$LOG_FILE"
  rsync -av --dry-run ${DELETE_OPTION} --inplace --files-from=/tmp/backup_file_list.txt --no-compress / "${BACKUP_DIR}/" | grep "deleting" | tee -a "$LOG_FILE"
  read -p "Do you want to proceed with deletion? (Y/N): " confirm
  if [[ ! $confirm =~ ^[Yy]$ ]]; then
    echo "Operation cancelled by user" | tee -a "$LOG_FILE"
    exit 0
  fi
fi

if ! rsync -av ${DELETE_OPTION} --inplace --files-from=/tmp/backup_file_list.txt --no-compress --progress --stats / "${BACKUP_DIR}/" 2>&1 | tee -a "$LOG_FILE"; then
  echo "ERROR: Rsync failed" | tee -a "$LOG_FILE"
  exit 1
fi

# Print backup statistics
echo "Sync statistics:" | tee -a "$LOG_FILE"
total_files=0
total_size=0
for dir in "$@"; do
  read -r files size <<<"$(get_stats "$dir")"
  total_files=$((total_files + files))
  total_size=$((total_size + size))
  echo "Source $dir: $files files, ${size} KB" | tee -a "$LOG_FILE"
done
read -r backup_files backup_size <<<"$(get_stats "${BACKUP_DIR}")"
echo "Sync directory: $backup_files files, ${backup_size} KB" | tee -a "$LOG_FILE"

# Verify file count and size
echo "Verifying file counts and sizes..." | tee -a "$LOG_FILE"
if [ "$total_files" -ne "$backup_files" ] || [ "$total_size" -ne "$backup_size" ]; then
  echo "ERROR: Sync verification failed" | tee -a "$LOG_FILE"
  echo "Source: $total_files files, ${total_size} KB" | tee -a "$LOG_FILE"
  echo "Sync: $backup_files files, ${backup_size} KB" | tee -a "$LOG_FILE"
  exit 1
fi
echo "Sync verification successful" | tee -a "$LOG_FILE"

if [ "${DEEP_VERIFY}" = true ]; then
  echo "Starting deep verification process..." | tee -a "$LOG_FILE"
  start_time=$(date +%s)

  echo "Calculating source hashes..." | tee -a "$LOG_FILE"
  find "$@" -type f -print0 | pv -l | xargs -0 -n 100 -P "${PROCESS_COUNT}" b3sum 2>/dev/null >/tmp/source_hashes.txt || {
    echo "ERROR: Source hash calculation failed" | tee -a "$LOG_FILE"
    exit 1
  }
  echo "Source hash calculation completed. Files processed: $(wc -l </tmp/source_hashes.txt)" | tee -a "$LOG_FILE"

  echo "Calculating backup hashes..." | tee -a "$LOG_FILE"
  cd "${BACKUP_DIR}" || exit 1
  find . -type f -print0 | pv -l | xargs -0 -n 100 -P "${PROCESS_COUNT}" b3sum 2>/dev/null | sed 's|^\./||' >/tmp/backup_hashes.txt || {
    echo "ERROR: Sync hash calculation failed" | tee -a "$LOG_FILE"
    exit 1
  }
  echo "Sync hash calculation completed. Files processed: $(wc -l </tmp/backup_hashes.txt)" | tee -a "$LOG_FILE"

  echo "Comparing hash files..." | tee -a "$LOG_FILE"
  if diff /tmp/source_hashes.txt /tmp/backup_hashes.txt >/dev/null; then
    echo "Verification successful - all files match" | tee -a "$LOG_FILE"
  else
    echo "Error: Deep verification failed" | tee -a "$LOG_FILE"
    echo "Mismatched files:" | tee -a "$LOG_FILE"
    diff --unified=0 /tmp/source_hashes.txt /tmp/backup_hashes.txt | grep -E "^\+|\-" | grep -v "@@" | tee -a "$LOG_FILE"
    echo "End of mismatched files list" | tee -a "$LOG_FILE"
    exit 1
  fi

  end_time=$(date +%s)
  echo "Deep verification completed in $((end_time - start_time)) seconds" | tee -a "$LOG_FILE"
fi

echo "Sync completed at $(date)" | tee -a "$LOG_FILE"

# Check log file permissions before compression
check_permissions "$LOG_FILE"
gzip -f "$LOG_FILE"
