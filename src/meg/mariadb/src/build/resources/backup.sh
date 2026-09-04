# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, renames the temporary file on success, prunes and sets the exit code. Define
# backup_written below, naming the backup with backup_target (or letting backup_files do both) and
# writing "${BACKUP_TARGET_PATH}.tmp". A snippet leaving the estate changed while it works, such as
# one stopping its own container, also defines backup_interrupted, called on INT, TERM or HUP but
# never on a backup that merely fails. Declare BACKUP_EXCLUDED as the paths this module deliberately
# does not back up, so backup_files reports only what neither it nor the declaration covers. Never
# assign another wrapper variable, prefix this snippet's own state with the module name, and expand
# a value read from .env as "${VAR:?}", so a missing key fails by name rather than corrupting the
# backup.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this, zero to never skip
# BACKUP_SERVICE_RESTART  start the service again after the copy, false when the caller starts it itself
# BACKUP_EXCLUDED         the paths deliberately not backed up, declared by this snippet

MARIADB_BACKUP_ATTEMPTS=3
MARIADB_BACKUP_BACKOFF=10

backup_written() {
  local attempt=1
  backup_target "${BACKUP_FULL_SUFFIX}" "sql.gz" || return 1
  while true; do
    if docker exec --user root "${BACKUP_MODULE_NAME}" bash -c '
set -o pipefail
mariadb-dump -uroot -p"${MARIADB_ROOT_PASSWORD:?}" --all-databases --single-transaction --quick | gzip
    ' >"${BACKUP_TARGET_PATH}.tmp"; then
      return 0
    fi
    [ "${attempt}" -lt "${MARIADB_BACKUP_ATTEMPTS}" ] || return 1
    echo "Dump failed on attempt [${attempt}] of [${MARIADB_BACKUP_ATTEMPTS}], retrying in [${MARIADB_BACKUP_BACKOFF}] seconds" >&2
    sleep "${MARIADB_BACKUP_BACKOFF}"
    attempt=$((attempt + 1))
  done
}
