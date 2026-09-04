backup_written() {
  backup_target "${BACKUP_FULL_SUFFIX}" "sql.gz" || return 1
  docker exec --user root "${BACKUP_MODULE_NAME}" bash -c '
set -o pipefail
pg_dumpall -U postgres | gzip
  ' >"${BACKUP_TARGET_PATH}.tmp"
}
