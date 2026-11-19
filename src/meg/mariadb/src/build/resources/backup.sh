# The engine (`supervisor backup run`) owns the run, this snippet owns the backup, as hooks each in its own bash.
# Define backup_written, naming the target with backup_target or backup_files and writing "${BACKUP_TARGET_PATH}.tmp".
# Optional hooks: backup_interrupted, backup_completed, backup_pruned_store, backup_versioned.
# No hook relies on a variable another set, own state is prefixed with the module name, .env values expand as "${VAR:?}".
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's data path
# BACKUP_SOURCE_VERSION   the version being backed up
# BACKUP_TARGET_PATH      this run's artefact path, set by backup_target
# BACKUP_RUN_TIMESTAMP    this run's timestamp
# BACKUP_FULL_SUFFIX      suffix of a full backup
# BACKUP_DELTA_SUFFIX     suffix of a delta backup, which needs a full one before it
# BACKUP_VERSIONED_NONE   what backup_versioned prints when a restore needs no software version
# BACKUP_SKIP_HOURS       skip when the newest backup is younger than this, zero never skips

MARIADB_BACKUP_ATTEMPTS=3
MARIADB_BACKUP_BACKOFF=10

backup_versioned() {
  docker exec "${BACKUP_MODULE_NAME}" mariadbd --version | sed -n 's/^.* Ver \([^ ]*\) .*$/\1/p'
}

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
