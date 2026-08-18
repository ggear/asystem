# Defines backup_written for this module, naming its backup with backup_target (or letting
# backup_files do both) and writing "${BACKUP_TARGET_PATH}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_MODULE_NAME      this module's name
# BACKUP_SOURCE_PATH      this module's source data path
# BACKUP_TARGET_PATH      this run's backup path, empty until backup_target names it
# BACKUP_RUN_TIMESTAMP    this run's timestamp, shared by the directory and the filename
# BACKUP_FULL_SUFFIX      the file suffix marking a full backup
# BACKUP_DELTA_SUFFIX     the file suffix marking a delta backup, requiring a full backup proceeding it
# BACKUP_RETAIN_DAYS      the window by which daily backups are retained before entering the pruning window
# BACKUP_SKIP_HOURS       skip the run when the newest backup is younger than this

INFLUXDB3_BACKUP_CLUSTER="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
INFLUXDB3_BACKUP_STORE="${BACKUP_SOURCE_PATH}/${INFLUXDB3_BACKUP_CLUSTER}/backups"

backup_stored() {
  [ -d "${INFLUXDB3_BACKUP_STORE}" ] || return 0
  find "${INFLUXDB3_BACKUP_STORE}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^(full|delta)-[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort -t- -k2
}

backup_status() {
  docker exec --user root "${BACKUP_MODULE_NAME}" influxdb3 status backup --name "$1" --format json 2>/dev/null |
    jq -r '.. | strings | select(test("^(completed|in_progress|failed)$"))' 2>/dev/null | head -1
}

backup_awaited() {
  local status
  while true; do
    status="$(backup_status "$1")"
    [ "${status}" = "completed" ] && return 0
    if [ "${status}" = "failed" ]; then
      echo "Backup failed [$1]" >&2
      return 1
    fi
    sleep 5
  done
}

backup_written() {
  local names parent full name
  mapfile -t names < <(backup_stored)
  parent=""
  full=""
  for name in "${names[@]}"; do
    case "${name}" in full-*) full="${name}" ;; esac
  done
  [ "${#names[@]}" -gt 0 ] && parent="${names[-1]}"
  if [ -n "${full}" ] &&
    [ "$(backup_epoch "${full}")" -ge "$(($(date +%s) - BACKUP_RETAIN_DAYS * 86400))" ] &&
    [ -n "${parent}" ] && [ "$(backup_status "${parent}")" = "completed" ]; then
    name="delta-${BACKUP_RUN_TIMESTAMP}"
    backup_target "${BACKUP_DELTA_SUFFIX}" "tar.gz" || return 1
    echo "Creating a delta backup from parent [${parent}]"
    docker exec --user root "${BACKUP_MODULE_NAME}" \
      influxdb3 create backup --name "${name}" --incremental --parent "${parent}" >/dev/null || return 1
  else
    name="full-${BACKUP_RUN_TIMESTAMP}"
    backup_target "${BACKUP_FULL_SUFFIX}" "tar.gz" || return 1
    [ -n "${full}" ] && echo "Starting a new full backup, previous full backup [${full}] is older than [${BACKUP_RETAIN_DAYS}] days"
    docker exec --user root "${BACKUP_MODULE_NAME}" \
      influxdb3 create backup --name "${name}" >/dev/null || return 1
  fi
  backup_awaited "${name}" || return 1
  tar --create --directory "${INFLUXDB3_BACKUP_STORE}" --file - -- "${name}" 2>/dev/null | gzip >"${BACKUP_TARGET_PATH}.tmp"
}
