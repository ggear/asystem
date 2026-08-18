# Defines backup_written for this module, naming its artifact with backup_target (or letting
# backup_files do both) and writing "${BACKUP_PUB_TARGET}.tmp". Read the wrapper variables below,
# never assign one, and prefix this snippet's own state with the module name.
#
# BACKUP_PUB_MODULE       this module's name, and its container's name
# BACKUP_PUB_SOURCE       this module's data directory
# BACKUP_PUB_DIR          the backup directory inside it, where artifacts land
# BACKUP_PUB_STAMP        this run's timestamp, shared by the directory and the filename
# BACKUP_PUB_FULL         the suffix marking a self-contained artifact
# BACKUP_PUB_DELTA        the suffix marking an artifact that needs the full before it
# BACKUP_PUB_RETAIN_DAYS  the dense window, in days
# BACKUP_PUB_TARGET       this run's artifact path, empty until backup_target names it

INFLUXDB3_BACKUP_CLUSTER="${INFLUXDB3_CLUSTER_ID:-cluster_1}"
INFLUXDB3_BACKUP_STORE="${BACKUP_PUB_SOURCE}/${INFLUXDB3_BACKUP_CLUSTER}/backups"

backup_stored() {
  [ -d "${INFLUXDB3_BACKUP_STORE}" ] || return 0
  find "${INFLUXDB3_BACKUP_STORE}" -maxdepth 1 -mindepth 1 -type d -printf '%f\n' 2>/dev/null |
    grep -E '^(full|delta)-[0-9]{4}-[0-9]{2}-[0-9]{2}_[0-9]{2}-[0-9]{2}-[0-9]{2}$' | sort -t- -k2
}

backup_status() {
  docker exec --user root "${BACKUP_PUB_MODULE}" influxdb3 status backup --name "$1" --format json 2>/dev/null |
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
    [ "$(backup_epoch "${full}")" -ge "$(($(date +%s) - BACKUP_PUB_RETAIN_DAYS * 86400))" ] &&
    [ -n "${parent}" ] && [ "$(backup_status "${parent}")" = "completed" ]; then
    name="delta-${BACKUP_PUB_STAMP}"
    backup_target "${BACKUP_PUB_DELTA}" "tar.gz" || return 1
    echo "Creating a delta backup from parent [${parent}]"
    docker exec --user root "${BACKUP_PUB_MODULE}" \
      influxdb3 create backup --name "${name}" --incremental --parent "${parent}" >/dev/null || return 1
  else
    name="full-${BACKUP_PUB_STAMP}"
    backup_target "${BACKUP_PUB_FULL}" "tar.gz" || return 1
    [ -n "${full}" ] && echo "Starting a new full backup, previous full backup [${full}] is older than [${BACKUP_PUB_RETAIN_DAYS}] days"
    docker exec --user root "${BACKUP_PUB_MODULE}" \
      influxdb3 create backup --name "${name}" >/dev/null || return 1
  fi
  backup_awaited "${name}" || return 1
  tar --create --directory "${INFLUXDB3_BACKUP_STORE}" --file - -- "${name}" 2>/dev/null | gzip >"${BACKUP_PUB_TARGET}.tmp"
}
