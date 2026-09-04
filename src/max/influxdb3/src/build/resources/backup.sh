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

backup_eligible() {
  [ -d "${BACKUP_INTERNAL_ROOT_DIR}/${1#*-}" ]
}

eval "influxdb3_pruned_local () $(declare -f backup_pruned | tail -n +2)"

influxdb3_pruned_server() {
  local names name live_full dead=() reversed=()
  mapfile -t names < <(backup_stored)
  live_full=""
  for name in "${names[@]}"; do
    case "${name}" in full-*) live_full="${name}" ;; esac
  done
  [ -n "${live_full}" ] || return 0
  local past_full=""
  for name in "${names[@]}"; do
    [ "${name}" = "${live_full}" ] && past_full=1
    [ -n "${past_full}" ] || dead+=("${name}")
  done
  [ "${#dead[@]}" -gt 0 ] || return 0
  for ((name = ${#dead[@]} - 1; name >= 0; name--)); do reversed+=("${dead[name]}"); done
  for name in "${reversed[@]}"; do
    case "${name}" in
    delta-*) docker exec --user root "${BACKUP_MODULE_NAME}" influxdb3 delete backup --name "${name}" --incremental >/dev/null 2>&1 || echo "Could not delete dead delta backup [${name}]" >&2 ;;
    esac
  done
  for name in "${dead[@]}"; do
    case "${name}" in
    full-*) docker exec --user root "${BACKUP_MODULE_NAME}" influxdb3 delete backup --name "${name}" >/dev/null 2>&1 || echo "Could not delete dead full backup [${name}]" >&2 ;;
    esac
  done
}

backup_pruned() {
  influxdb3_pruned_local "$@"
  influxdb3_pruned_server
}

backup_written() {
  local names parent full name
  mapfile -t names < <(backup_stored)
  parent=""
  full=""
  for name in "${names[@]}"; do
    backup_eligible "${name}" || continue
    parent="${name}"
    case "${name}" in full-*) full="${name}" ;; esac
  done
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
