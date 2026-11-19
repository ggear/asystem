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

backup_versioned() {
  docker exec --user root "${BACKUP_MODULE_NAME}" psql -U postgres -Atc \
    "SELECT current_setting('server_version_num')::int / 10000 || '-' || extversion FROM pg_extension WHERE extname = 'timescaledb'"
}

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
