# The wrapper owns the run, this snippet owns the backup. The wrapper checks the throttle, calls
# backup_written, checks the archive's integrity, renames the temporary file on success, prunes and
# sets the exit code. Define backup_written below, naming the backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". A snippet copying files passes
# backup_files a root under BACKUP_SOURCE_PATH and the names of its include and exclude arrays, an
# absent include fails the backup and whatever under the root neither array covers is reported. A
# snippet leaving the estate changed while it works, such as one stopping its own container, also
# defines backup_interrupted, called on INT, TERM or HUP but never on a backup that merely fails, and
# backup_completed, called once the archive has been named and kept whatever the outcome, whose
# non-zero return fails the run without discarding the archive. Never assign another wrapper
# variable, prefix this snippet's own state with the module name, and expand a value read from .env
# as "${VAR:?}", so a missing key fails by name rather than corrupting the backup.
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

POSTGRES_BACKUP_SKIPPED=(
  "wrangle"
)
POSTGRES_BACKUP_TRANSIENT=(
  "hass:public.event_data"
  "hass:public.events"
  "hass:public.state_attributes"
  "hass:public.states"
  "hass:public.statistics_short_term"
)

backup_written() {
  local databases database skipped table excluded
  backup_target "${BACKUP_FULL_SUFFIX}" "sql.gz" || return 1
  mapfile -t databases < <(docker exec --user root "${BACKUP_MODULE_NAME}" \
    psql -U postgres -d postgres -Atc "SELECT datname FROM pg_database WHERE datallowconn ORDER BY datname")
  if [ "${#databases[@]}" -eq 0 ]; then
    echo "Listed no databases in [${BACKUP_MODULE_NAME}]" >&2
    return 1
  fi
  {
    docker exec --user root "${BACKUP_MODULE_NAME}" pg_dumpall -U postgres --globals-only || exit 1
    for database in "${databases[@]}"; do
      skipped="false"
      for table in "${POSTGRES_BACKUP_SKIPPED[@]}"; do
        [ "${table}" = "${database}" ] && skipped="true"
      done
      if [ "${skipped}" = "true" ]; then
        echo "Skipped database [${database}], it is rebuilt rather than restored" >&2
        continue
      fi
      excluded=()
      for table in "${POSTGRES_BACKUP_TRANSIENT[@]}"; do
        [ "${table%%:*}" = "${database}" ] && excluded+=("--exclude-table-data=${table#*:}")
      done
      case "${database}" in
      postgres | template1)
        printf '\\connect %s\n\n' "${database}"
        docker exec --user root "${BACKUP_MODULE_NAME}" pg_dump -U postgres "${excluded[@]}" "${database}" || exit 1
        ;;
      *)
        docker exec --user root "${BACKUP_MODULE_NAME}" pg_dump -U postgres --create "${excluded[@]}" "${database}" || exit 1
        ;;
      esac
    done
  } | gzip >"${BACKUP_TARGET_PATH}.tmp"
}
