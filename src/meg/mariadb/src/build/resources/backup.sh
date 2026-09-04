# Defines backup_written for this module, naming its backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_SOURCE_VERSION   the version the backup was extracted from
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this

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
