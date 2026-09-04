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
